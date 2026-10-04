"""Aegis tool-call security for LangChain agents.

    from langchain.agents import create_agent
    from aegis_sdk_langchain import secure_middleware

    agent = create_agent(model, tools, middleware=[secure_middleware(mode="enforce")])

Every tool call is evaluated by the local Aegis engine before it runs and
tagged ``runtime_kind="langchain"`` on the shared audit chain. ``observe``
(default) logs only; ``enforce`` short-circuits a blocked call with a
``ToolMessage`` instead of raising, so the run is not crashed.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from ._core import (  # noqa: F401  (re-exported for callers)
    MODE_ENFORCE,
    MODE_OBSERVE,
    AegisClient,
    Verdict,
    normalize_tool_name,
    resolve_mode,
)

__all__ = [
    "secure_middleware",
    "AegisCallbackHandler",
    "AegisClient",
    "Verdict",
    "MODE_ENFORCE",
    "MODE_OBSERVE",
]

_RUNTIME_KIND = "langchain"
_ENV_HEADLESS = "AEGIS_HEADLESS"
_TRUTHY = {"1", "true", "yes", "on"}


def _headless() -> bool:
    return str(os.environ.get(_ENV_HEADLESS, "")).strip().lower() in _TRUTHY


def _tool_call_parts(tool_call: Any) -> tuple[str, Any, Optional[str]]:
    """Extract (name, args, id) from a dict- or attr-shaped tool call."""
    if isinstance(tool_call, dict):
        name = tool_call.get("name") or tool_call.get("tool") or ""
        args = tool_call.get("args")
        call_id = tool_call.get("id") or tool_call.get("tool_call_id")
    else:
        name = getattr(tool_call, "name", "") or ""
        args = getattr(tool_call, "args", None)
        call_id = getattr(tool_call, "id", None) or getattr(tool_call, "tool_call_id", None)
    return str(name), args, (str(call_id) if call_id else None)


def _evaluate(client: AegisClient, mode: str, fail_closed: bool, tool_call: Any, session_id: Optional[str]):
    name, args, call_id = _tool_call_parts(tool_call)
    verdict = client.evaluate(name, args, session_id=session_id, headless=_headless())
    run, reason = verdict.decisive(mode, fail_closed=fail_closed)
    return name, args, call_id, verdict, run, reason


def secure_middleware(
    mode: Optional[str] = None,
    *,
    client: Optional[AegisClient] = None,
    session_id: Optional[str] = None,
    fail_closed: bool = True,
):
    """Return a LangChain ``AgentMiddleware`` that gates tool calls via Aegis.

    Args:
        mode: ``"observe"`` (default, log-only) or ``"enforce"`` (block).
        client: reuse an :class:`AegisClient`; one is created otherwise.
        session_id: forwarded to the engine for per-session policy/JIT grants.
        fail_closed: in enforce mode, deny when the engine is unreachable.
    """
    resolved = resolve_mode(mode)
    cli = client or AegisClient(runtime_kind=_RUNTIME_KIND)

    try:  # imported lazily so the package installs without langchain present
        from langchain.agents.middleware import AgentMiddleware
        from langchain_core.messages import ToolMessage
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "aegis-sdk-langchain needs langchain>=1.0 (langchain.agents.middleware). "
            "Install with: pip install 'aegis-sdk-langchain[langchain]'"
        ) from exc

    def _blocked_message(name: str, reason: str, call_id: Optional[str]) -> Any:
        return ToolMessage(
            content=f"Aegis Guard: blocked `{name}` — {reason}",
            tool_call_id=call_id or name,
            status="error",
        )

    class AegisGuardMiddleware(AgentMiddleware):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            tool_call = getattr(request, "tool_call", request)
            name, args, call_id, verdict, run, reason = _evaluate(
                cli, resolved, fail_closed, tool_call, session_id
            )
            if not run:
                cli.audit(name, tool_input=args, action="block", reason=reason,
                          session_id=session_id, risk_score=verdict.risk_score,
                          pipeline=verdict.raw)
                return _blocked_message(name, reason, call_id)
            if verdict.action != "allow":
                cli.audit(name, tool_input=args, action=verdict.action, reason=verdict.reason,
                          session_id=session_id, risk_score=verdict.risk_score,
                          pipeline=verdict.raw)
            return handler(request)

        async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            tool_call = getattr(request, "tool_call", request)
            name, args, call_id, verdict, run, reason = _evaluate(
                cli, resolved, fail_closed, tool_call, session_id
            )
            if not run:
                cli.audit(name, tool_input=args, action="block", reason=reason,
                          session_id=session_id, risk_score=verdict.risk_score,
                          pipeline=verdict.raw)
                return _blocked_message(name, reason, call_id)
            if verdict.action != "allow":
                cli.audit(name, tool_input=args, action=verdict.action, reason=verdict.reason,
                          session_id=session_id, risk_score=verdict.risk_score,
                          pipeline=verdict.raw)
            return await handler(request)

    return AegisGuardMiddleware()


def AegisCallbackHandler(*args: Any, **kwargs: Any):
    """Observe-only handler for legacy AgentExecutor / LCEL chains.

    Logs every tool call to the audit chain but never blocks — middleware is
    the blocking path. Instantiates a subclass of ``BaseCallbackHandler``; the
    langchain-core import happens here so importing this module stays cheap.
    """
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "AegisCallbackHandler needs langchain-core. Install with: "
            "pip install 'aegis-sdk-langchain[langchain]'"
        ) from exc

    cli = kwargs.pop("client", None) or AegisClient(runtime_kind=_RUNTIME_KIND)
    session_id = kwargs.pop("session_id", None)

    class _Handler(BaseCallbackHandler):
        def on_tool_start(self, serialized: Any, input_str: Any, **kw: Any) -> None:
            name = (serialized or {}).get("name") if isinstance(serialized, dict) else None
            verdict = cli.evaluate(name or "", input_str, session_id=session_id, headless=_headless())
            if verdict.action != "allow":
                cli.audit(name or "", tool_input=input_str, action=verdict.action,
                          reason=verdict.reason, session_id=session_id,
                          risk_score=verdict.risk_score, pipeline=verdict.raw)

    return _Handler(*args, **kwargs)
