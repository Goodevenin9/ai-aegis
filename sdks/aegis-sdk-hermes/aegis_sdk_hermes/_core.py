"""Aegis SDK shared core — the single source of truth for the framework SDKs.

This module is vendored (byte-identical) into each ``aegis_sdk_<framework>``
package as ``_core.py`` so every SDK is self-contained and installs cleanly
with ``pip install aegis-sdk-<framework> --no-deps``. A lockstep test enforces
that the copies stay identical; run ``sdks/sync_core.py`` after editing here.

It implements the *same* HTTP contract the CLI plugins use, so SDK tool calls
land on the same tamper-evident audit chain (tagged ``runtime_kind``) and go
through the same controls:

    GET  {base}/api/tool-permissions/synced-overrides?runtime=<kind>
    POST {base}/api/egress/evaluate
    POST {base}/api/runtime/pretool/decide
    POST {base}/api/tool-permissions/call-audit     (deny/ask audit row)
    POST {base}/api/jit/requests                    (requestable deny)

Design: pure standard library (``urllib``), no third-party dependency, so the
adapter-only install path works. Every network path is fail-open *at the
transport layer* — a missing/!2xx/timed-out response yields ``{}`` — and the
observe/enforce policy is applied by the caller via :meth:`Verdict.decide`.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "DEFAULT_BASE_URL",
    "MODE_OBSERVE",
    "MODE_ENFORCE",
    "ENV_BASE_URL",
    "ENV_API_KEY",
    "ENV_MODE",
    "Verdict",
    "AegisClient",
    "normalize_tool_name",
    "resolve_base_url",
    "resolve_mode",
]

DEFAULT_BASE_URL = "http://127.0.0.1:8741"
ENV_BASE_URL = "AEGIS_ENGINE_ENDPOINT"
ENV_API_KEY = "AEGIS_API_KEY"
ENV_MODE = "AEGIS_SDK_MODE"

MODE_OBSERVE = "observe"
MODE_ENFORCE = "enforce"

ACTION_ALLOW = "allow"
ACTION_CONFIRM = "confirm"
ACTION_BLOCK = "block"

# Read budget per call. Loopback, so sub-second; kept tunable because a first
# connection on a cold interpreter can be slower than the steady state.
DEFAULT_TIMEOUT_S = 0.5
OVERRIDES_CACHE_TTL_S = 5.0

# Mirrors NETWORK_CAPABLE_BUILTINS in the CLI plugins / core/egress. Only these
# pay the (slightly larger) egress round-trip; everything else short-circuits.
NETWORK_CAPABLE = frozenset(
    {
        "webfetch",
        "websearch",
        "bash",
        "powershell",
        "shell",
        "exec",
        "terminal",
        "run_terminal_cmd",
        "runcommand",
        "execute_command",
    }
)

_MCP_PREFIX = "mcp__"


def resolve_base_url(explicit: Optional[str] = None) -> str:
    """Engine endpoint: explicit arg > ``AEGIS_ENGINE_ENDPOINT`` > loopback."""
    value = (explicit or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).strip()
    return value.rstrip("/") or DEFAULT_BASE_URL


def resolve_mode(explicit: Optional[str] = None) -> str:
    """Return ``observe`` or ``enforce`` (default observe). Unknown → observe."""
    value = (explicit or os.environ.get(ENV_MODE) or MODE_OBSERVE).strip().lower()
    return MODE_ENFORCE if value == MODE_ENFORCE else MODE_OBSERVE


def normalize_tool_name(name: Any) -> list[str]:
    """Canonical candidate tool ids, most-specific first.

    ``mcp__server__tool`` → ``["server:tool", "tool"]``; anything else is
    returned as-is (framework tools have arbitrary names, unlike the CLI
    builtins). Non-strings and empties yield ``[]`` (→ allow, fail-open).
    """
    if not isinstance(name, str) or not name:
        return []
    if name.startswith(_MCP_PREFIX):
        rest = name[len(_MCP_PREFIX) :]
        sep = rest.find("__")
        if sep == -1:
            return []
        server, tool = rest[:sep], rest[sep + 2 :]
        if not server or not tool:
            return []
        return [f"{server}:{tool}", tool]
    return [name]


def _is_network_capable(tool_name: str) -> bool:
    n = str(tool_name or "").lower()
    return n in NETWORK_CAPABLE or n.startswith(_MCP_PREFIX)


@dataclass(frozen=True)
class Verdict:
    """The outcome of evaluating one tool call.

    ``action`` is the engine's verdict (``allow`` / ``confirm`` / ``block``).
    ``reachable`` records whether the engine actually answered; it is what
    distinguishes a genuine ``allow`` from a fail-open default.
    """

    action: str
    reason: Optional[str] = None
    risk_score: Optional[float] = None
    drift_score: Optional[float] = None
    drift_level: Optional[str] = None
    tool_id: Optional[str] = None
    base_decision: str = ACTION_ALLOW
    reachable: bool = True
    headless_escalated: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.action == ACTION_BLOCK

    @property
    def needs_confirmation(self) -> bool:
        return self.action == ACTION_CONFIRM

    def decisive(self, mode: str, *, fail_closed: bool = False) -> tuple[bool, str]:
        """Return ``(run, reason)`` for a call under ``mode``.

        observe → always run (log-only). enforce → run iff the verdict is not
        ``block``; if the engine was unreachable the call is denied
        (fail-closed) because the control cannot be silently bypassed.
        """
        if mode != MODE_ENFORCE:
            return True, "observe: log-only"
        if not self.reachable:
            return (False, "enforce: engine unreachable (fail-closed)") if fail_closed else (
                True,
                "enforce: engine unreachable (fail-open)",
            )
        if self.blocked:
            return False, self.reason or "blocked by policy"
        return True, self.reason or "allowed"


class AegisClient:
    """Thin, synchronous client for one Aegis engine endpoint.

    One instance per app; it is thread-safe (the overrides cache is guarded).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        runtime_kind: str = "unknown",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        overrides_ttl_s: float = OVERRIDES_CACHE_TTL_S,
    ) -> None:
        self.base_url = resolve_base_url(base_url)
        self.api_key = (api_key or os.environ.get(ENV_API_KEY) or "").strip()
        self.runtime_kind = runtime_kind
        self.timeout_s = float(timeout_s)
        self.overrides_ttl_s = float(overrides_ttl_s)
        self._lock = threading.Lock()
        self._overrides: dict[str, Any] = {}
        self._overrides_at = 0.0

    # -- transport ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self, path: str, *, body: Optional[dict] = None, timeout_s: Optional[float] = None
    ) -> dict:
        """GET (body None) / POST, returning ``{}`` on ANY failure (fail-open)."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers())
        if data is None:
            req.method = "GET"
        try:
            timeout = self.timeout_s if timeout_s is None else timeout_s
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if not 200 <= getattr(resp, "status", 200) < 300:
                    return {}
                raw = resp.read()
            parsed = json.loads(raw.decode("utf-8", "replace")) if raw else {}
            return parsed if isinstance(parsed, dict) else {}
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return {}

    def _post_async(self, path: str, body: dict) -> None:
        """Fire-and-forget POST on a NON-daemon thread.

        Non-daemon is load-bearing: a blocked-call audit row is the single
        highest-value record, and the interpreter joins non-daemon threads at
        exit, so a short agent run cannot terminate before the POST flushes.
        A daemon thread here silently drops audit rows whenever the process
        exits promptly (observed in real-framework e2e). The request is bounded
        by ``timeout_s``, so a hung engine delays exit by at most that long.
        """
        threading.Thread(
            target=self._request, args=(path,), kwargs={"body": body}, daemon=False
        ).start()

    # -- engine calls ------------------------------------------------------
    def synced_overrides(self) -> dict:
        now = time.monotonic()
        with self._lock:
            if self._overrides and (now - self._overrides_at) < self.overrides_ttl_s:
                return self._overrides
        data = self._request(
            f"/api/tool-permissions/synced-overrides?runtime={self.runtime_kind}"
        )
        with self._lock:
            self._overrides = data
            self._overrides_at = now
        return data

    @staticmethod
    def _match_override(candidates: Sequence[str], overrides: Mapping[str, Any]) -> Optional[dict]:
        rows = overrides.get("synced") if isinstance(overrides, Mapping) else None
        if not isinstance(rows, list):
            return None
        index: dict[str, dict] = {}
        for row in rows:
            if isinstance(row, Mapping) and isinstance(row.get("tool_id"), str):
                index.setdefault(row["tool_id"].lower(), dict(row))
        for cand in candidates:
            hit = index.get(cand.lower())
            if hit is not None:
                return hit
        return None

    def evaluate(
        self,
        tool_name: str,
        tool_input: Any = None,
        *,
        base_decision: str = ACTION_ALLOW,
        allowed_capabilities: Iterable[str] = (),
        project_root: Optional[str] = None,
        headless: bool = False,
        session_id: Optional[str] = None,
        candidates: Optional[Sequence[str]] = None,
    ) -> Verdict:
        """Run the same three controls the CLI plugins run, in one call."""
        cands = list(candidates) if candidates is not None else normalize_tool_name(tool_name)

        # 1) local permission rules (name-based, synced from the app)
        base = base_decision
        if cands:
            match = self._match_override(cands, self.synced_overrides())
            if match:
                effect = str(match.get("effect", "")).lower()
                if effect == "deny":
                    base = ACTION_BLOCK
                elif effect == "prompt":
                    base = ACTION_CONFIRM

        # 2) egress (destination-based) for network-capable tools only
        if base == ACTION_ALLOW and _is_network_capable(tool_name):
            egress = self._request(
                "/api/egress/evaluate",
                body={
                    "tool_name": tool_name,
                    "tool_input": tool_input or {},
                    "runtime_kind": self.runtime_kind,
                    "session_id": session_id or "__anonymous__",
                },
            )
            egress_action = str(egress.get("action", "")).lower()
            if egress_action == ACTION_BLOCK:
                base = ACTION_BLOCK
            elif egress_action == ACTION_CONFIRM:
                base = ACTION_CONFIRM

        # 3) deterministic five-stage pipeline
        pipeline = self._request(
            "/api/runtime/pretool/decide",
            body={
                "tool_name": tool_name,
                "tool_input": tool_input or {},
                "runtime_kind": self.runtime_kind,
                "session_id": session_id or "__anonymous__",
                "base_decision": base,
                "allowed_capabilities": list(allowed_capabilities),
                "project_root": project_root,
                "headless": bool(headless),
            },
        )
        reachable = bool(pipeline)
        action = str(pipeline.get("action") or base).lower()
        if action not in (ACTION_ALLOW, ACTION_CONFIRM, ACTION_BLOCK):
            action = base
        reason = pipeline.get("reason")
        return Verdict(
            action=action,
            reason=reason if isinstance(reason, str) else None,
            risk_score=_as_number(pipeline.get("risk_score")),
            drift_score=_as_number(pipeline.get("drift_score")),
            drift_level=pipeline.get("drift_level") if isinstance(pipeline.get("drift_level"), str) else None,
            tool_id=(cands[0] if cands else None),
            base_decision=base,
            reachable=reachable,
            headless_escalated=pipeline.get("headless_escalated") is True,
            raw=pipeline,
        )

    def audit(
        self,
        tool_name: str,
        *,
        tool_id: Optional[str] = None,
        tool_input: Any = None,
        action: str,
        reason: Optional[str] = None,
        session_id: Optional[str] = None,
        risk_score: Optional[float] = None,
        pipeline: Optional[Mapping[str, Any]] = None,
        is_essential: bool = False,
    ) -> None:
        """Write an audit row for a non-allow decision (fire-and-forget)."""
        cands = [tool_id] if tool_id else normalize_tool_name(tool_name)
        body = {
            "tool_id": cands[0] if cands else tool_name,
            "function_name": tool_name,
            "action": _decision_to_audit_action(action),
            "risk": _risk_band(risk_score),
            "reason": _audit_reason(reason, pipeline),
            "is_essential": bool(is_essential),
            "args_preview": _preview(tool_input),
            "runtime_kind": self.runtime_kind,
            "session_id": session_id or None,
        }
        self._post_async("/api/tool-permissions/call-audit", body)

    def request_access(self, tool_name: str, *, session_id: Optional[str] = None) -> None:
        """File a JIT access request for a requestable deny (fire-and-forget)."""
        cands = normalize_tool_name(tool_name)
        self._post_async(
            "/api/jit/requests",
            {
                "tool_id": cands[0] if cands else tool_name,
                "function_name": tool_name,
                "runtime_kind": self.runtime_kind,
                "session_id": session_id,
            },
        )

    def ping(self) -> bool:
        return bool(self._request("/health"))


def _as_number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _decision_to_audit_action(decision: str) -> str:
    return {"block": "block", "confirm": "log_only", "allow": "allow"}.get(decision, "log_only")


def _risk_band(score: Optional[float]) -> Optional[str]:
    if not isinstance(score, (int, float)):
        return None
    if score >= 80:
        return "admin"
    if score >= 60:
        return "delete"
    if score >= 40:
        return "write"
    return "read"


def _preview(tool_input: Any, limit: int = 200) -> Optional[str]:
    if tool_input is None:
        return None
    try:
        raw = tool_input if isinstance(tool_input, str) else json.dumps(tool_input)
    except (TypeError, ValueError):
        return None
    return raw[:limit]


def _audit_reason(reason: Optional[str], pipeline: Optional[Mapping[str, Any]]) -> Optional[str]:
    text = reason if isinstance(reason, str) and reason else None
    if not isinstance(pipeline, Mapping):
        return text
    layers: dict[str, Any] = {}
    raw_layers = pipeline.get("layers")
    if isinstance(raw_layers, Mapping):
        for name, value in raw_layers.items():
            layers[name] = value.get("value") if isinstance(value, Mapping) else None
    signals = pipeline.get("signals")
    return json.dumps(
        {
            "schema": "aegis.pretool-pipeline.v1",
            "summary": text,
            "risk_score": _as_number(pipeline.get("risk_score")),
            "drift_score": _as_number(pipeline.get("drift_score")),
            "drift_level": pipeline.get("drift_level"),
            "base_decision": pipeline.get("base_decision"),
            "final_action": pipeline.get("action"),
            "headless_escalated": pipeline.get("headless_escalated") is True,
            "layers": layers,
            "signals": [
                {
                    "layer": s.get("layer"),
                    "code": s.get("code"),
                    "severity": s.get("severity"),
                    "score": s.get("score"),
                }
                for s in (signals if isinstance(signals, list) else [])
                if isinstance(s, Mapping)
            ],
        }
    )
