"""Hermes plugin surface: the guard object, its block directive, and install().

Hermes's plugin contract (as declared by ``hermes_agent.plugins``) is a
``pre_tool_call`` hook that may return a block directive. We stay defensive
about the exact host shape: the plugin object exposes both a ``pre_tool_call``
method and a module-level ``register`` factory so either registration style
works, and ``install()`` attaches to the tool-registry dispatch for library
embeddings.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from ._core import AegisClient, Verdict, resolve_mode
from .tool_id import resolve_candidates

_RUNTIME_KIND = "hermes"
_ENV_HEADLESS = "AEGIS_HEADLESS"
_TRUTHY = {"1", "true", "yes", "on"}


def _headless() -> bool:
    return str(os.environ.get(_ENV_HEADLESS, "")).strip().lower() in _TRUTHY


class AegisGuard:
    """Holds the client + posture; the single decision point for Hermes calls."""

    def __init__(
        self,
        mode: Optional[str] = None,
        *,
        client: Optional[AegisClient] = None,
        session_id: Optional[str] = None,
        fail_closed: bool = True,
    ) -> None:
        self.mode = resolve_mode(mode)
        self.client = client or AegisClient(runtime_kind=_RUNTIME_KIND)
        self.session_id = session_id
        self.fail_closed = fail_closed

    def check(self, tool_name: str, args: Any = None,
              session_id: Optional[str] = None) -> tuple[bool, str, Verdict]:
        """Return ``(run, reason, verdict)`` for one Hermes tool call."""
        verdict = self.client.evaluate(
            tool_name,
            args,
            session_id=session_id or self.session_id,
            headless=_headless(),
            candidates=resolve_candidates(tool_name),
        )
        run, reason = verdict.decisive(self.mode, fail_closed=self.fail_closed)
        return run, reason, verdict

    def pre_tool_call(self, tool_name: str = "", args: Any = None,
                      session_id: str = "", **_: Any) -> Optional[dict]:
        """Hermes ``pre_tool_call`` hook → a block directive, or ``None`` to allow.

        Hermes passes ``tool_name`` / ``args`` (a dict) / ``session_id`` / … as
        keyword arguments and reads ``{"action": "block", "message": ...}``
        (see ``hermes_cli.plugins._get_pre_tool_call_directive_details`` — a
        block directive MUST carry a non-empty ``message``). In observe mode
        the tool always runs, so this never returns a directive.
        """
        run, reason, verdict = self.check(tool_name, args, session_id=session_id or None)
        if verdict.action != "allow":
            self.client.audit(tool_name, tool_input=args, action=verdict.action, reason=verdict.reason,
                              session_id=session_id or self.session_id, risk_score=verdict.risk_score,
                              pipeline=verdict.raw)
        if run:
            return None
        return {"action": "block", "message": f"Aegis Guard: {reason}"}


# The object the entry point exposes to Hermes's plugin manager.
plugin = AegisGuard()


def register(ctx: Any = None, **kwargs: Any) -> AegisGuard:
    """Entry-point factory: ``hermes_agent.plugins`` → ``...plugin:register``.

    Hermes calls ``register(ctx)`` after loading the entry point; ``ctx`` is a
    ``PluginContext`` exposing ``register_hook(name, callback)``.
    """
    guard = AegisGuard(**kwargs)
    if ctx is not None and hasattr(ctx, "register_hook"):
        try:
            ctx.register_hook("pre_tool_call", guard.pre_tool_call)
        except Exception:  # noqa: BLE001 - never break host startup
            pass
    return guard


def install(
    mode: Optional[str] = None,
    *,
    client: Optional[AegisClient] = None,
    session_id: Optional[str] = None,
    fail_closed: bool = True,
    attach: bool = True,
) -> AegisGuard:
    """Attach the guard for library embeddings (no plugin manager).

    Registers ``pre_tool_call`` on the live Hermes ``PluginManager`` so the
    guard sits beneath Hermes's own dangerous-command approval (which is known
    to fail open in gateway/headless contexts). Returns the guard regardless;
    call ``guard.pre_tool_call`` yourself if the manager is unavailable.
    """
    guard = AegisGuard(mode=mode, client=client, session_id=session_id, fail_closed=fail_closed)
    if not attach:
        return guard
    try:  # pragma: no cover - depends on the installed hermes-agent
        from hermes_cli.plugins import get_plugin_manager  # type: ignore

        manager = get_plugin_manager()
        hooks = getattr(manager, "_hooks", None)
        if isinstance(hooks, dict):
            hooks.setdefault("pre_tool_call", []).append(guard.pre_tool_call)
    except Exception:  # noqa: BLE001
        pass
    return guard
