"""Five-stage semantic decision pipeline for Agent ``PreToolUse`` events.

The module is intentionally independent from the existing detection engines.
It consumes their decision as ``base_decision`` and may only preserve or
strengthen it.  Deterministic code owns every score, transition and final
decision.  An LLM may contribute only closed-vocabulary boolean
``SemanticLabels`` that are queued on a session before a tool call reaches
this hot path.

Pipeline: Boundary -> Capability -> Radius -> Drift -> Friction.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, FrozenSet, Literal, Mapping, Optional

from aegis.app.services.chinese_security_rules import match_chinese_boundary
from aegis.app.services.immune_learning import BehaviorProfile, ImmuneMatcher

DecisionAction = Literal["allow", "confirm", "block"]
BaseDecision = Literal["allow", "ask", "deny"]

_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_WHITESPACE = re.compile(r"\s+")
_URL = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)


def normalize_security_text(value: str) -> str:
    """Return a stable representation for deterministic security matching."""

    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = _ZERO_WIDTH.sub("", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


@dataclass(frozen=True)
class Signal:
    """One explainable observation; signals never perform side effects."""

    layer: str
    code: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    message: str
    score: int = 0
    evidence: Optional[str] = None


@dataclass(frozen=True)
class SemanticLabels:
    """Discrete, untrusted semantic evidence produced by an optional LLM."""

    theme_shifted: bool = False
    permission_probing: bool = False
    request_escalation: bool = False
    explicit_harm: bool = False
    unauthorized_target: bool = False
    deception_or_evasion: bool = False
    irreversible_impact: bool = False
    # Set only by the optional focused verifier, never by the primary extractor.
    harm_verified: bool = False


IntentRadius = Literal["none", "project", "local", "user", "system", "external"]
KNOWN_CAPABILITIES = frozenset(
    {"file_read", "file_write", "shell_exec", "network_outbound", "unknown_tool"}
)


@dataclass(frozen=True)
class IntentEvidence:
    """Closed-vocabulary semantic evidence; it contains no score or verdict."""

    labels: SemanticLabels = SemanticLabels()
    requested_capabilities: FrozenSet[str] = frozenset()
    requested_radius: IntentRadius = "none"


@dataclass
class TrustGrant:
    expires_at: float
    remaining_uses: int


@dataclass(frozen=True)
class PipelineConfig:
    """Deterministic weights and thresholds; safe to expose as configuration."""

    confirm_threshold: int = 40
    block_threshold: int = 80
    # A single semantic label remains below the balanced friction threshold;
    # two independent labels or a repeated label are required to intervene.
    theme_shift_weight: int = 20
    permission_probe_weight: int = 20
    request_escalation_weight: int = 20
    # One fallible model label is evidence, not user friction. Repeated turns
    # or independent deterministic signals may still cross the thresholds.
    explicit_harm_weight: int = 20
    # AgentHarm calibration keeps the noisier semantic dimensions in shadow
    # mode.  They remain observable and can be enabled by an explicit policy.
    unauthorized_target_weight: int = 0
    deception_or_evasion_weight: int = 0
    irreversible_impact_weight: int = 5
    harm_verified_weight: int = 20
    intent_capability_weight: int = 10
    repeated_retry_weight: int = 15
    third_retry_weight: int = 30
    safe_turn_decay: int = 10
    max_drift_score: int = 100
    # Learned patterns are evidence, never an autonomous verdict.  Even after
    # repeated matches their lifetime contribution stays below confirm_threshold.
    max_immune_session_score: int = 25

    @classmethod
    def for_preset(cls, preset: str) -> "PipelineConfig":
        """Return an auditable intervention profile without hidden heuristics."""

        profiles = {
            "observe": {
                "confirm_threshold": 70,
                "block_threshold": 95,
                "explicit_harm_weight": 15,
            },
            "balanced": {},
            "strict": {
                "confirm_threshold": 30,
                "block_threshold": 65,
                "explicit_harm_weight": 20,
            },
        }
        try:
            return cls(**profiles[preset])
        except KeyError as exc:
            raise ValueError(f"unknown pipeline preset: {preset}") from exc


@dataclass(frozen=True)
class PreToolContext:
    """Normalized input contract shared by all runtime adapters."""

    tool_name: str
    tool_input: Mapping[str, Any]
    session_id: str
    runtime_kind: str
    base_decision: BaseDecision = "allow"
    allowed_capabilities: FrozenSet[str] = frozenset()
    project_root: Optional[Path] = None
    headless: bool = False


@dataclass(frozen=True)
class LayerResult:
    """Stable output of one pipeline stage."""

    value: str
    signals: tuple[Signal, ...] = ()
    critical: bool = False
    requires_confirmation: bool = False


@dataclass(frozen=True)
class PipelineDecision:
    """Final Friction decision plus the evidence used to reach it."""

    action: DecisionAction
    risk_score: int
    drift_score: int
    drift_level: str
    reason: str
    signals: tuple[Signal, ...]
    layers: Mapping[str, LayerResult]
    base_decision: BaseDecision
    headless_escalated: bool = False
    immune_matches: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "risk_score": self.risk_score,
            "drift_score": self.drift_score,
            "drift_level": self.drift_level,
            "reason": self.reason,
            "base_decision": self.base_decision,
            "explanation": _explanation_zh(self.action, self.signals, self.drift_score),
            "headless_escalated": self.headless_escalated,
            "immune_matches": [dict(match) for match in self.immune_matches],
            "signals": [signal.__dict__ for signal in self.signals],
            "layers": {
                name: {
                    "value": result.value,
                    "critical": result.critical,
                    "requires_confirmation": result.requires_confirmation,
                    "signals": [signal.__dict__ for signal in result.signals],
                }
                for name, result in self.layers.items()
            },
        }


@dataclass
class SessionState:
    """Small deterministic state machine state for one runtime session."""

    drift_score: int = 0
    attempts: Counter[str] = field(default_factory=Counter)
    pending_labels: list[SemanticLabels] = field(default_factory=list)
    pending_intent_evidence: list[IntentEvidence] = field(default_factory=list)
    original_intent: Optional[str] = None
    latest_intent: Optional[str] = None
    intent_revision: int = 0
    scored_intent_boundary_revision: int = 0
    allowed_capabilities: FrozenSet[str] = frozenset()
    trust_grants: dict[str, TrustGrant] = field(default_factory=dict)
    immune_score_total: int = 0
    tool_history: list[str] = field(default_factory=list)
    capability_history: list[str] = field(default_factory=list)
    radius_history: list[str] = field(default_factory=list)
    effect_history: list[str] = field(default_factory=list)
    active_semantic_flags: set[str] = field(default_factory=set)
    semantic_context_remaining: int = 0


class SessionDriftStore:
    """In-process session store.

    The store is deliberately behind a narrow interface so a later persistence
    adapter can rebuild it from the existing hash-chain audit log without
    changing the five pipeline stages.
    """

    def __init__(self, max_sessions: int = 1000, max_pending_labels: int = 8) -> None:
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._max_sessions = max(1, max_sessions)
        self._max_pending_labels = max(1, max_pending_labels)

    def get(self, session_id: str) -> SessionState:
        key = session_id or "__anonymous__"
        state = self._sessions.get(key)
        if state is None:
            state = SessionState()
            self._sessions[key] = state
            if len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
        else:
            self._sessions.move_to_end(key)
        return state

    def observe_intent(
        self,
        session_id: str,
        text: str,
        allowed_capabilities: FrozenSet[str] = frozenset(),
    ) -> SessionState:
        state = self.get(session_id)
        normalized_intent = normalize_security_text(text)[:16000]
        if state.original_intent is None and normalized_intent:
            state.original_intent = normalized_intent
        if normalized_intent:
            state.latest_intent = normalized_intent
            state.intent_revision += 1
        if allowed_capabilities:
            state.allowed_capabilities = allowed_capabilities
        return state

    def observe_semantic_labels(self, session_id: str, labels: SemanticLabels) -> None:
        """P0 compatibility adapter for Drift-only evidence producers."""

        self.observe_intent_evidence(session_id, IntentEvidence(labels=labels))

    def observe_intent_evidence(self, session_id: str, evidence: IntentEvidence) -> None:
        pending = self.get(session_id).pending_intent_evidence
        pending.append(evidence)
        del pending[: -self._max_pending_labels]

    def consume_semantic_labels(self, session_id: str) -> tuple[SemanticLabels, ...]:
        """P0 compatibility adapter; consume only the Drift label projection."""

        state = self.get(session_id)
        evidence = self.consume_intent_evidence(session_id)
        labels = tuple(state.pending_labels) + tuple(item.labels for item in evidence)
        state.pending_labels.clear()
        return labels

    def consume_intent_evidence(self, session_id: str) -> tuple[IntentEvidence, ...]:
        state = self.get(session_id)
        evidence = tuple(state.pending_intent_evidence)
        state.pending_intent_evidence.clear()
        return evidence

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id or "__anonymous__", None)

    def grant_trust(
        self,
        session_id: str,
        capability: str,
        ttl_seconds: int = 300,
        max_uses: int = 5,
    ) -> None:
        if capability not in KNOWN_CAPABILITIES:
            raise ValueError(f"unknown capability: {capability}")
        state = self.get(session_id)
        state.trust_grants[capability] = TrustGrant(
            expires_at=time.time() + max(1, min(int(ttl_seconds), 3600)),
            remaining_uses=max(1, min(int(max_uses), 100)),
        )

    def consume_trusted_capability(self, session_id: str, capability: str) -> bool:
        state = self.get(session_id)
        now = time.time()
        grant = state.trust_grants.get(capability)
        if not grant:
            return False
        if grant.expires_at <= now or grant.remaining_uses <= 0:
            state.trust_grants.pop(capability, None)
            return False
        grant.remaining_uses -= 1
        if grant.remaining_uses <= 0:
            state.trust_grants.pop(capability, None)
        return True

    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Return the complete deterministic state in JSON-compatible form."""

        state = self.get(session_id)
        return {
            "drift_score": state.drift_score,
            "attempts": dict(state.attempts),
            "pending_labels": [label.__dict__.copy() for label in state.pending_labels],
            "pending_intent_evidence": [
                {
                    "labels": item.labels.__dict__.copy(),
                    "requested_capabilities": sorted(item.requested_capabilities),
                    "requested_radius": item.requested_radius,
                }
                for item in state.pending_intent_evidence
            ],
            "original_intent": state.original_intent,
            "latest_intent": state.latest_intent,
            "intent_revision": state.intent_revision,
            "scored_intent_boundary_revision": state.scored_intent_boundary_revision,
            "allowed_capabilities": sorted(state.allowed_capabilities),
            "trust_grants": {
                capability: {
                    "expires_at": grant.expires_at,
                    "remaining_uses": grant.remaining_uses,
                }
                for capability, grant in state.trust_grants.items()
                if grant.expires_at > time.time() and grant.remaining_uses > 0
            },
            "immune_score_total": state.immune_score_total,
            "tool_history": list(state.tool_history[-32:]),
            "capability_history": list(state.capability_history[-32:]),
            "radius_history": list(state.radius_history[-32:]),
            "effect_history": list(state.effect_history[-32:]),
            "active_semantic_flags": sorted(state.active_semantic_flags),
            "semantic_context_remaining": state.semantic_context_remaining,
        }

    def restore(self, session_id: str, value: Mapping[str, Any]) -> SessionState:
        """Restore a validated snapshot, clamping untrusted persisted values."""

        pending: list[SemanticLabels] = []
        for raw in list(value.get("pending_labels") or [])[: self._max_pending_labels]:
            if isinstance(raw, Mapping):
                pending.append(
                    SemanticLabels(
                        theme_shifted=bool(raw.get("theme_shifted", False)),
                        permission_probing=bool(raw.get("permission_probing", False)),
                        request_escalation=bool(raw.get("request_escalation", False)),
                        explicit_harm=raw.get("explicit_harm") is True,
                        unauthorized_target=raw.get("unauthorized_target") is True,
                        deception_or_evasion=raw.get("deception_or_evasion") is True,
                        irreversible_impact=raw.get("irreversible_impact") is True,
                        harm_verified=raw.get("harm_verified") is True,
                    )
                )
        pending_evidence: list[IntentEvidence] = []
        for raw in list(value.get("pending_intent_evidence") or [])[: self._max_pending_labels]:
            if not isinstance(raw, Mapping):
                continue
            raw_labels = raw.get("labels") if isinstance(raw.get("labels"), Mapping) else {}
            capabilities = frozenset(
                str(item) for item in list(raw.get("requested_capabilities") or [])
                if str(item) in KNOWN_CAPABILITIES
            )
            radius = str(raw.get("requested_radius") or "none")
            if radius not in {"none", "project", "local", "user", "system", "external"}:
                radius = "none"
            pending_evidence.append(
                IntentEvidence(
                    labels=SemanticLabels(
                        theme_shifted=bool(raw_labels.get("theme_shifted", False)),
                        permission_probing=bool(raw_labels.get("permission_probing", False)),
                        request_escalation=bool(raw_labels.get("request_escalation", False)),
                        explicit_harm=raw_labels.get("explicit_harm") is True,
                        unauthorized_target=raw_labels.get("unauthorized_target") is True,
                        deception_or_evasion=raw_labels.get("deception_or_evasion") is True,
                        irreversible_impact=raw_labels.get("irreversible_impact") is True,
                        harm_verified=raw_labels.get("harm_verified") is True,
                    ),
                    requested_capabilities=capabilities,
                    requested_radius=radius,  # type: ignore[arg-type]
                )
            )
        raw_attempts = value.get("attempts") or {}
        attempts = Counter()
        if isinstance(raw_attempts, Mapping):
            for key, count in raw_attempts.items():
                try:
                    attempts[str(key)[:128]] = max(0, min(1000, int(count)))
                except (TypeError, ValueError):
                    continue
        state = SessionState(
            drift_score=max(0, min(100, int(value.get("drift_score", 0) or 0))),
            attempts=attempts,
            pending_labels=pending,
            pending_intent_evidence=pending_evidence,
            original_intent=(str(value["original_intent"])[:16000]
                             if value.get("original_intent") else None),
            latest_intent=(str(value["latest_intent"])[:16000]
                           if value.get("latest_intent") else None),
            intent_revision=max(0, int(value.get("intent_revision", 0) or 0)),
            scored_intent_boundary_revision=max(
                0, int(value.get("scored_intent_boundary_revision", 0) or 0)
            ),
            allowed_capabilities=frozenset(
                str(item)[:100] for item in list(value.get("allowed_capabilities") or [])[:32]
                if str(item).strip()
            ),
            trust_grants={
                str(capability): TrustGrant(
                    expires_at=float(raw.get("expires_at", 0)),
                    remaining_uses=max(0, min(100, int(raw.get("remaining_uses", 0)))),
                )
                for capability, raw in dict(value.get("trust_grants") or {}).items()
                if capability in KNOWN_CAPABILITIES and isinstance(raw, Mapping)
                and float(raw.get("expires_at", 0) or 0) > time.time()
            },
            immune_score_total=max(
                0, min(30, int(value.get("immune_score_total", 0) or 0))
            ),
            tool_history=[str(item)[:100] for item in list(value.get("tool_history") or [])[-32:]],
            capability_history=[
                str(item)[:100] for item in list(value.get("capability_history") or [])[-32:]
            ],
            radius_history=[
                str(item)[:32] for item in list(value.get("radius_history") or [])[-32:]
            ],
            effect_history=[
                str(item)[:32] for item in list(value.get("effect_history") or [])[-32:]
            ],
            active_semantic_flags={
                str(item) for item in list(value.get("active_semantic_flags") or [])
                if str(item) in {
                    "explicit_harm", "unauthorized_target", "deception_or_evasion",
                    "irreversible_impact", "harm_verified",
                }
            },
            semantic_context_remaining=max(
                0, min(16, int(value.get("semantic_context_remaining", 0) or 0))
            ),
        )
        key = session_id or "__anonymous__"
        self._sessions[key] = state
        self._sessions.move_to_end(key)
        if len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
        return state


_TOOL_CAPABILITIES: dict[str, str] = {
    "read": "file_read",
    "grep": "file_read",
    "glob": "file_read",
    "ls": "file_read",
    "write": "file_write",
    "edit": "file_write",
    "multiedit": "file_write",
    "notebookedit": "file_write",
    "bash": "shell_exec",
    "powershell": "shell_exec",
    "shell": "shell_exec",
    "exec": "shell_exec",
    "terminal": "shell_exec",
    "webfetch": "network_outbound",
    "websearch": "network_outbound",
}


@dataclass(frozen=True)
class ToolEffectProfile:
    """Deterministic side-effect facts used as independent evidence."""

    category: str = "unknown"
    external_write: bool = False
    high_impact: bool = False
    sensitive_read: bool = False


def tool_effect_profile(tool_name: str) -> ToolEffectProfile:
    """Classify a tool by generic action semantics, not benchmark case IDs."""

    lowered = str(tool_name or "").lower()
    leaf = lowered.rsplit("__", 1)[-1]
    if any(token in leaf for token in ("delete", "ransomware", "malware", "encrypt", "wipe", "overwrite")):
        return ToolEffectProfile("destructive", high_impact=True)
    if any(token in leaf for token in ("transfer", "purchase", "order", "payment", "paypal", "crypto")):
        return ToolEffectProfile("financial", external_write=True, high_impact=True)
    if any(token in leaf for token in ("login_data", "credential", "password", "secret", "token")):
        return ToolEffectProfile("credential_access", high_impact=True, sensitive_read=True)
    if any(token in leaf for token in ("terminal", "exec", "shell", "powershell", "bash")):
        return ToolEffectProfile("software_execution", high_impact=True)
    if any(token in leaf for token in ("send", "post", "upload", "message", "comment", "reply", "submit", "follow", "repost", "share")):
        return ToolEffectProfile("external_write", external_write=True)
    if any(token in leaf for token in ("email", "contact", "database", "transaction", "friends_info", "credit_card")):
        return ToolEffectProfile("sensitive_read", sensitive_read=True)
    if any(token in leaf for token in ("read", "get", "query", "search", "download", "list")):
        return ToolEffectProfile("read_only")
    return ToolEffectProfile()


def _input_text(tool_input: Mapping[str, Any]) -> str:
    try:
        return normalize_security_text(json.dumps(tool_input, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return normalize_security_text(str(tool_input))


def _boundary(context: PreToolContext, state: SessionState) -> LayerResult:
    text = _input_text(context.tool_input)
    lowered = text.lower()
    signals: list[Signal] = []

    critical_patterns = (
        (
            "boundary.root_delete",
            re.compile(
                r"\brm\s+(?:-[a-z]*r[a-z]*\s+|-[a-z]*f[a-z]*\s+){1,2}"
                r"/(?=\s|[\"',}\]]|$)",
                re.I,
            ),
            "Recursive root deletion",
        ),
        (
            "boundary.curl_pipe_shell",
            re.compile(r"\b(?:curl|wget)\b[^|]{0,500}\|\s*(?:ba)?sh\b", re.I),
            "Remote content piped to a shell",
        ),
        (
            "boundary.shadow_file",
            re.compile(r"(?:/etc/shadow|[\\/]\.ssh[\\/](?:id_rsa|id_ed25519))", re.I),
            "Credential file access",
        ),
        (
            "boundary.disk_overwrite",
            re.compile(r"\bdd\b[^\n]{0,300}\bof=/dev/(?:sd[a-z]|nvme\d+n\d+)", re.I),
            "Raw disk overwrite",
        ),
    )
    for code, pattern, message in critical_patterns:
        if pattern.search(lowered):
            signals.append(Signal("boundary", code, "critical", message, 100, text[:240]))

    obfuscation_patterns = (
        ("boundary.eval_download", re.compile(r"\beval\b[^\n]{0,300}\b(?:curl|wget)\b", re.I)),
        (
            "boundary.decode_execute",
            re.compile(
                r"\b(?:base64\s+-d|xxd\s+-r|frombase64string)\b[^|]{0,300}\|\s*(?:ba)?sh\b", re.I
            ),
        ),
        (
            "boundary.encoded_powershell",
            re.compile(r"\bpowershell(?:\.exe)?\b[^\n]{0,200}-(?:enc|encodedcommand)\b", re.I),
        ),
    )
    for code, pattern in obfuscation_patterns:
        if pattern.search(lowered):
            signals.append(
                Signal("boundary", code, "high", "Command obfuscation signal", 15, text[:240])
            )

    tool_matches = match_chinese_boundary(text)
    for index, match in enumerate(tool_matches):
        signals.append(
            Signal(
                "boundary", match.code + ".tool_input", match.severity,
                match.message,
                100 if match.severity == "critical" else (15 if index == 0 else 0),
                text[:240],
            )
        )
    intent_text = state.latest_intent or ""
    intent_matches = match_chinese_boundary(intent_text)
    for index, match in enumerate(intent_matches):
        signals.append(
            Signal(
                "boundary",
                match.code + ".intent",
                match.severity,
                match.message + " in current intent",
                100 if match.severity == "critical" else (15 if index == 0 else 0),
                f"intent_revision:{state.intent_revision}",
            )
        )

    critical = any(signal.severity == "critical" for signal in signals)
    value = "critical" if critical else ("suspicious" if signals else "clear")
    return LayerResult(value=value, signals=tuple(signals), critical=critical)


def _tool_capability(tool_name: str) -> Optional[str]:
    lowered = tool_name.lower()
    if lowered.startswith("mcp__"):
        return "network_outbound"
    return _TOOL_CAPABILITIES.get(lowered)


def required_capability(tool_name: str) -> str:
    """Public adapter contract used by runtime policy and approval flows."""

    return _tool_capability(tool_name) or "unknown_tool"


def _capability(
    context: PreToolContext,
    state: SessionState,
    intent_evidence: tuple[IntentEvidence, ...] = (),
    config: Optional[PipelineConfig] = None,
) -> LayerResult:
    config = config or PipelineConfig()
    required = _tool_capability(context.tool_name)
    allowed = context.allowed_capabilities or state.allowed_capabilities
    if not required:
        required = "unknown_tool"
    if not allowed:
        # Secure default for the prototype: routine reads remain frictionless,
        # while mutating, shell and network capabilities require an explicit
        # manifest or confirmation.
        allowed = frozenset({"file_read"})
    signals: list[Signal] = []
    if required not in allowed:
        signals.append(
            Signal(
                "capability",
                "capability.undeclared",
                "medium",
                f"Tool requires undeclared capability: {required}",
                20,
                required,
            )
        )
    implicit = sorted(
        {cap for item in intent_evidence for cap in item.requested_capabilities if cap not in allowed}
    )
    if implicit:
        signals.append(
            Signal(
                "capability",
                "capability.intent_undeclared",
                "medium",
                "Intent requests undeclared capabilities: " + ", ".join(implicit),
                config.intent_capability_weight,
                ",".join(implicit),
            )
        )
    effect = tool_effect_profile(context.tool_name)
    harm_context = bool(
        state.active_semantic_flags & {"explicit_harm", "harm_verified"}
    ) and state.semantic_context_remaining > 0
    if harm_context and effect.high_impact:
        signals.append(Signal(
            "capability", "capability.harmful_high_impact", "high",
            f"Harmful intent is being operationalized through {effect.category}",
            20, effect.category,
        ))
    elif harm_context and effect.external_write:
        signals.append(Signal(
            "capability", "capability.harmful_external_write", "medium",
            "Harmful intent is being delivered outside the current session",
            10, effect.category,
        ))
    return LayerResult(
        value=required,
        signals=tuple(signals),
        # A structured tool call outside the manifest is deterministic and
        # asks immediately. An LLM-inferred capability is fallible evidence;
        # it must combine with another signal or repeat before Friction acts.
        requires_confirmation=any(
            signal.code == "capability.undeclared" for signal in signals
        ),
    )


_PATH_KEYS = frozenset({"path", "file_path", "filepath", "directory", "cwd", "notebook_path"})


def _paths_from_input(value: Any, key: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            paths.extend(_paths_from_input(child_value, str(child_key).lower()))
    elif isinstance(value, (list, tuple)):
        for child in value:
            paths.extend(_paths_from_input(child, key))
    elif isinstance(value, str) and key in _PATH_KEYS:
        paths.append(value)
    return paths


def _path_radius(raw_path: str, project_root: Optional[Path]) -> str:
    expanded = Path(raw_path).expanduser()
    if project_root:
        root = project_root.resolve(strict=False)
        candidate = expanded if expanded.is_absolute() else root / expanded
        try:
            candidate.resolve(strict=False).relative_to(root)
            return "project"
        except ValueError:
            pass
    lowered = str(expanded).replace("\\", "/").lower()
    if lowered.startswith(("/etc/", "/usr/", "/var/", "c:/windows/", "c:/program files/")):
        return "system"
    if "/users/" in lowered or lowered.startswith("~") or lowered.startswith("/home/"):
        return "user"
    return "local"


def _radius(
    context: PreToolContext,
    intent_evidence: tuple[IntentEvidence, ...] = (),
) -> LayerResult:
    signals: list[Signal] = []
    observed_radii = [
        _path_radius(path, context.project_root) for path in _paths_from_input(context.tool_input)
    ]
    text = _input_text(context.tool_input)
    if _URL.search(text) or context.tool_name.lower().startswith("mcp__"):
        observed_radii.append("external")
    priority = {"project": 0, "local": 1, "user": 2, "system": 3, "external": 4}
    inferred = [item.requested_radius for item in intent_evidence if item.requested_radius != "none"]
    radii = observed_radii + inferred
    value = max(radii, key=lambda radius: priority[radius]) if radii else "local"
    observed_value = (
        max(observed_radii, key=lambda radius: priority[radius])
        if observed_radii else "local"
    )
    if observed_value in {"user", "system", "external"}:
        score = {"user": 10, "system": 20, "external": 15}[observed_value]
        signals.append(
            Signal(
                "radius", f"radius.{observed_value}", "medium",
                f"Operation radius: {observed_value}", score,
            )
        )
    for inferred_radius in sorted(set(inferred), key=lambda item: priority[item]):
        if inferred_radius in {"user", "system", "external"}:
            signals.append(
                Signal(
                    "radius",
                    f"radius.intent_{inferred_radius}",
                    "medium",
                    f"Intent requests {inferred_radius} radius",
                    {"user": 10, "system": 20, "external": 15}[inferred_radius],
                    inferred_radius,
                )
            )
    return LayerResult(value=value, signals=tuple(signals))


def _fingerprint(context: PreToolContext, signals: tuple[Signal, ...]) -> str:
    """Fingerprint a risk pattern, not exact arguments, so small retries correlate."""

    codes = ",".join(sorted({signal.code for signal in signals}))
    material = f"{_tool_capability(context.tool_name) or context.tool_name.lower()}\0{codes}"
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _drift(
    context: PreToolContext,
    store: SessionDriftStore,
    upstream_signals: tuple[Signal, ...],
    config: PipelineConfig,
    semantic_labels: tuple[SemanticLabels, ...] = (),
    immune_matches: tuple[Mapping[str, Any], ...] = (),
) -> LayerResult:
    state = store.get(context.session_id)
    signals: list[Signal] = []

    immune_remaining = max(0, config.max_immune_session_score - state.immune_score_total)
    for match in immune_matches:
        requested_delta = max(0, int(match.get("score_delta", 0) or 0))
        effective = bool(match.get("effective", False)) and requested_delta > 0
        applied_delta = min(requested_delta, immune_remaining) if effective else 0
        immune_remaining -= applied_delta
        state.immune_score_total += applied_delta
        # Keep the public/persisted match history aligned with the score that
        # actually entered this session.  The original requested contribution
        # remains available for explainability after the session cap is hit.
        if isinstance(match, dict):
            match["requested_score_delta"] = requested_delta
            match["score_delta"] = applied_delta
            match["effective"] = applied_delta > 0
        signals.append(
            Signal(
                "drift",
                "drift.immune_match" if applied_delta > 0 else "drift.immune_shadow_match",
                "medium" if applied_delta > 0 else "info",
                (
                    f"Confirmed attack pattern matched: {match.get('name', 'antibody')}"
                    if applied_delta > 0
                    else f"Shadow antibody observed: {match.get('name', 'antibody')}"
                ),
                applied_delta,
                str(match.get("antibody_id", ""))[:128],
            )
        )

    for labels in semantic_labels:
        if labels.explicit_harm:
            signals.append(Signal("drift", "drift.explicit_harm", "high",
                                  "Explicit harmful action requested", config.explicit_harm_weight))
        if labels.unauthorized_target:
            signals.append(Signal(
                "drift", "drift.unauthorized_target", "high",
                "A third-party target or asset lacks trusted authorization",
                config.unauthorized_target_weight,
            ))
        if labels.deception_or_evasion:
            signals.append(Signal(
                "drift", "drift.deception_or_evasion", "high",
                "Deception, concealment, or control evasion requested",
                config.deception_or_evasion_weight,
            ))
        if labels.irreversible_impact:
            signals.append(Signal(
                "drift", "drift.irreversible_impact", "high",
                "Requested effect is difficult to reverse",
                config.irreversible_impact_weight,
            ))
        if labels.harm_verified:
            signals.append(Signal(
                "drift", "drift.harm_verified", "high",
                "Focused semantic verifier confirmed concrete harm",
                config.harm_verified_weight,
            ))
        if labels.theme_shifted:
            signals.append(
                Signal(
                    "drift",
                    "drift.theme_shift",
                    "high",
                    "Conversation theme shifted",
                    config.theme_shift_weight,
                )
            )
        if labels.permission_probing:
            signals.append(
                Signal(
                    "drift",
                    "drift.permission_probing",
                    "high",
                    "Permission probing detected",
                    config.permission_probe_weight,
                )
            )
        if labels.request_escalation:
            signals.append(
                Signal(
                    "drift",
                    "drift.request_escalation",
                    "high",
                    "Requested capability escalated",
                    config.request_escalation_weight,
                )
            )

    effect = tool_effect_profile(context.tool_name)
    if (
        state.semantic_context_remaining > 0
        and state.active_semantic_flags & {"explicit_harm", "harm_verified"}
        and effect.external_write
        and "sensitive_read" in state.effect_history
    ):
        signals.append(Signal(
            "drift", "drift.sensitive_to_external_sequence", "high",
            "Sensitive data access was followed by an external write",
            15, "sensitive_read->external_write",
        ))

    if context.base_decision == "ask":
        signals.append(
            Signal(
                "drift",
                "drift.base_confirmation",
                "medium",
                "AI Aegis requested confirmation",
                10,
            )
        )
    elif context.base_decision == "deny":
        signals.append(
            Signal(
                "drift",
                "drift.base_block",
                "high",
                "AI Aegis blocked the attempted action",
                20,
            )
        )
    semantic_anomaly = any(
        signal.score > 0 and signal.code in {
            "drift.theme_shift", "drift.permission_probing", "drift.request_escalation",
            "drift.unauthorized_target", "drift.deception_or_evasion",
            "drift.irreversible_impact", "drift.harm_verified",
        }
        for signal in signals
    )
    has_capability_anomaly = any(
        signal.code == "capability.undeclared" for signal in upstream_signals
    )
    intent_boundary_is_new = state.intent_revision > state.scored_intent_boundary_revision
    drift_worthy = tuple(
        signal
        for signal in upstream_signals
        if (
            signal.layer in {"boundary", "capability"}
            and (not signal.code.endswith(".intent") or intent_boundary_is_new)
        )
        or signal.code in {"radius.user", "radius.system"}
        or (signal.code == "radius.external" and (semantic_anomaly or has_capability_anomaly))
    )
    if any(signal.layer == "boundary" and signal.code.endswith(".intent") for signal in drift_worthy):
        state.scored_intent_boundary_revision = state.intent_revision
    risky = any(signal.score > 0 for signal in drift_worthy)
    fingerprint = _fingerprint(context, drift_worthy)
    if risky:
        state.attempts[fingerprint] += 1
        attempt = state.attempts[fingerprint]
        if attempt >= 2:
            penalty = config.third_retry_weight if attempt >= 3 else config.repeated_retry_weight
            signals.append(
                Signal(
                    "drift",
                    "drift.repeated_risky_action",
                    "high",
                    f"Risky action repeated {attempt} times",
                    penalty,
                    fingerprint[:12],
                )
            )

    increment = sum(signal.score for signal in drift_worthy)
    increment += sum(signal.score for signal in signals)
    if increment == 0 and context.base_decision == "allow":
        state.drift_score = max(0, state.drift_score - config.safe_turn_decay)
        # Safe activity cools retry memory gradually. Clearing the whole map
        # would let an attacker interleave harmless reads between probes.
        for fingerprint in tuple(state.attempts):
            state.attempts[fingerprint] -= 1
            if state.attempts[fingerprint] <= 0:
                del state.attempts[fingerprint]
    state.drift_score = min(config.max_drift_score, state.drift_score + increment)
    if state.drift_score >= config.block_threshold:
        value = "critical"
    elif state.drift_score >= config.confirm_threshold:
        value = "elevated"
    elif state.drift_score > 0:
        value = "guarded"
    else:
        value = "normal"
    return LayerResult(value=value, signals=tuple(signals))


def _reason(
    action: DecisionAction, signals: tuple[Signal, ...], drift_score: int, risk_score: int
) -> str:
    important = [
        signal.message for signal in signals if signal.severity in {"critical", "high", "medium"}
    ]
    detail = "; ".join(dict.fromkeys(important[:3]))
    if detail:
        return f"Five-stage pipeline {action}: {detail} (risk={risk_score}, drift={drift_score})"
    return f"Five-stage pipeline {action} (risk={risk_score}, drift={drift_score})"


def _explanation_zh(
    action: DecisionAction,
    signals: tuple[Signal, ...],
    drift_score: int,
) -> dict[str, Any]:
    conclusion = {
        "allow": "当前证据不足以限制本次操作，允许执行。",
        "confirm": "检测到能力、范围或会话漂移风险，需要用户确认。",
        "block": "检测到高风险边界或累积漂移，已阻止执行。",
    }[action]
    evidence = [
        {
            "layer": signal.layer,
            "code": signal.code,
            "severity": signal.severity,
            "description": signal.message,
            "evidence": signal.evidence,
        }
        for signal in signals
        if signal.severity in {"medium", "high", "critical"}
    ]
    return {
        "language": "zh-CN",
        "conclusion": conclusion,
        "drift_score": drift_score,
        "evidence": evidence,
        "disclaimer": "结论由确定性五段管线生成；LLM只提供封闭枚举语义证据。",
    }


def run_pretool_pipeline(
    context: PreToolContext,
    store: SessionDriftStore,
    config: Optional[PipelineConfig] = None,
    immune_matcher: Optional[ImmuneMatcher] = None,
) -> PipelineDecision:
    """Run all five stages and return the sole Friction decision."""

    config = config or PipelineConfig()
    state = store.get(context.session_id)
    intent_evidence = store.consume_intent_evidence(context.session_id)
    legacy_labels = tuple(state.pending_labels)
    state.pending_labels.clear()
    semantic_labels = legacy_labels + tuple(item.labels for item in intent_evidence)
    semantic_flag_names = (
        "explicit_harm", "unauthorized_target", "deception_or_evasion",
        "irreversible_impact", "harm_verified",
    )
    observed_flags = {
        name for labels in semantic_labels for name in semantic_flag_names
        if getattr(labels, name)
    }
    if observed_flags:
        state.active_semantic_flags.update(observed_flags)
        state.semantic_context_remaining = 8
    boundary = _boundary(context, state)
    capability = _capability(context, state, intent_evidence, config)
    radius = _radius(context, intent_evidence)
    pre_drift_signals = boundary.signals + capability.signals + radius.signals
    immune_result = None
    if immune_matcher is not None:
        features = {signal.code for signal in pre_drift_signals}
        if any("shadow_file" in code for code in features):
            features.add("sensitive_read")
        if any("encoded" in code or "obfusc" in code or "decode" in code for code in features):
            features.add("obfuscation")
        if any(signal.layer == "capability" for signal in pre_drift_signals):
            features.add("capability_escalation")
        if radius.value in {"user", "system", "external"}:
            features.add("radius_expansion")
        if any(count > 0 for count in state.attempts.values()):
            features.add("repeated_retry")
        current_capability = required_capability(context.tool_name)
        profile = BehaviorProfile(
            tool_sequence=tuple((state.tool_history + [context.tool_name])[-32:]),
            capability_sequence=tuple(
                (state.capability_history + [current_capability])[-32:]
            ),
            radius_sequence=tuple((state.radius_history + [radius.value])[-32:]),
            features=frozenset(features),
        )
        immune_result = immune_matcher.match(profile)
    immune_matches = tuple(
        {
            "antibody_id": match.antibody_id,
            "name": match.name,
            "status": match.status,
            "similarity": match.similarity,
            "score_delta": match.score_delta,
            "effective": match.effective,
            "matched_features": list(match.matched_features),
        }
        for match in (immune_result.matches if immune_result else ())
    )
    drift = _drift(
        context,
        store,
        pre_drift_signals,
        config,
        semantic_labels,
        immune_matches,
    )
    signals = pre_drift_signals + drift.signals
    state.tool_history = (state.tool_history + [context.tool_name])[-32:]
    state.capability_history = (
        state.capability_history + [required_capability(context.tool_name)]
    )[-32:]
    state.radius_history = (state.radius_history + [radius.value])[-32:]
    state.effect_history = (
        state.effect_history + [tool_effect_profile(context.tool_name).category]
    )[-32:]
    if state.semantic_context_remaining > 0:
        state.semantic_context_remaining -= 1
        if state.semantic_context_remaining == 0:
            state.active_semantic_flags.clear()

    needs_confirmation = capability.requires_confirmation or context.base_decision == "ask"
    if boundary.critical or context.base_decision == "deny":
        action: DecisionAction = "block"
    elif store.get(context.session_id).drift_score >= config.block_threshold:
        action = "block"
    elif (
        store.get(context.session_id).drift_score >= config.confirm_threshold or needs_confirmation
    ):
        action = "confirm"
    else:
        action = "allow"

    headless_escalated = context.headless and action == "confirm"
    if headless_escalated:
        action = "block"
        signals += (
            Signal(
                "friction",
                "friction.headless_escalation",
                "high",
                "Confirmation escalated in headless mode",
                0,
            ),
        )

    drift_score = store.get(context.session_id).drift_score
    risk_score = min(100, max(drift_score, *(signal.score for signal in signals), 0))
    friction = LayerResult(
        value=action, signals=tuple(signal for signal in signals if signal.layer == "friction")
    )
    layers = {
        "boundary": boundary,
        "capability": capability,
        "radius": radius,
        "drift": drift,
        "friction": friction,
    }
    return PipelineDecision(
        action=action,
        risk_score=risk_score,
        drift_score=drift_score,
        drift_level=drift.value,
        reason=_reason(action, signals, drift_score, risk_score),
        signals=signals,
        layers=layers,
        base_decision=context.base_decision,
        headless_escalated=headless_escalated,
        immune_matches=immune_matches,
    )


__all__ = [
    "LayerResult",
    "IntentEvidence",
    "KNOWN_CAPABILITIES",
    "PipelineConfig",
    "PipelineDecision",
    "PreToolContext",
    "SemanticLabels",
    "SessionDriftStore",
    "Signal",
    "ToolEffectProfile",
    "normalize_security_text",
    "required_capability",
    "run_pretool_pipeline",
    "tool_effect_profile",
]
