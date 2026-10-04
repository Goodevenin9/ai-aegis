"""Aegis tool-call security for LangGraph-backed agents.

    from langchain.agents import create_agent  # langgraph-backed
    from aegis_sdk_langgraph import secure_middleware

    agent = create_agent(model, tools, middleware=[secure_middleware(mode="enforce")])

``langgraph.prebuilt.create_react_agent`` does not accept middleware; use
``create_agent`` (or gate a raw ``StateGraph`` tool node with ``interrupt()``).
Decisions are tagged ``runtime_kind="langgraph"`` on the shared audit chain.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from ._core import (  # noqa: F401
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

_RUNTIME_KIND = "langgraph"
_ENV_HEADLESS = "AEGIS_HEADLESS"
_TRUTHY = {"1", "true", "yes", "on"}


def _headless() -> bool:
    return str(os.environ.get(_ENV_HEADLESS, "")).strip().lower() in _TRUTHY


def _tool_call_parts(tool_call: Any) -> tuple[str, Any, Optional[str]]:
    if isinstance(tool_call, dict):
        name = tool_call.get("name") or tool_call.get("tool") or ""
        args = tool_call.get("args")
        call_id = tool_call.get("id") or tool_call.get("tool_call_id")
    else:
        name = getattr(tool_call, "name", "") or ""
        args = getattr(tool_call, "args", None)
        call_id = getattr(tool_call, "id", None) or getattr(tool_call, "tool_call_id", None)
    return str(name), args, (str(call_id) if call_id else None)


def secure_middleware(
    mode: Optional[str] = None,
    *,
    client: Optional[AegisClient] = None,
    session_id: Optional[str] = None,
    fail_closed: bool = True,
):
    """Return a LangGraph-backed ``AgentMiddleware`` gating tool calls via Aegis."""
    resolved = resolve_mode(mode)
    cli = client or AegisClient(runtime_kind=_RUNTIME_KIND)

    try:
        from langchain.agents.middleware import AgentMiddleware
        from langchain_core.messages import ToolMessage
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "aegis-sdk-langgraph needs langchain>=1.0 (the langgraph-backed create_agent). "
            "Install with: pip install 'aegis-sdk-langgraph[langgraph]'"
        ) from exc

    def _run(tool_call: Any):
        name, args, call_id = _tool_call_parts(tool_call)
        verdict = cli.evaluate(name, args, session_id=session_id, headless=_headless())
        run, reason = verdict.decisive(resolved, fail_closed=fail_closed)
        return name, args, call_id, verdict, run, reason

    def _blocked(name: str, reason: str, call_id: Optional[str]) -> Any:
        return ToolMessage(
            content=f"Aegis Guard: blocked `{name}` — {reason}",
            tool_call_id=call_id or name,
            status="error",
        )

    class AegisGuardMiddleware(AgentMiddleware):
        def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            name, args, call_id, verdict, run, reason = _run(getattr(request, "tool_call", request))
            if not run:
                cli.audit(name, tool_input=args, action="block", reason=reason,
                          session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
                return _blocked(name, reason, call_id)
            if verdict.action != "allow":
                cli.audit(name, tool_input=args, action=verdict.action, reason=verdict.reason,
                          session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
            return handler(request)

        async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
            name, args, call_id, verdict, run, reason = _run(getattr(request, "tool_call", request))
            if not run:
                cli.audit(name, tool_input=args, action="block", reason=reason,
                          session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
                return _blocked(name, reason, call_id)
            if verdict.action != "allow":
                cli.audit(name, tool_input=args, action=verdict.action, reason=verdict.reason,
                          session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
            return await handler(request)

    return AegisGuardMiddleware()


def AegisCallbackHandler(*args: Any, **kwargs: Any):
    """Observe-only handler for raw ``StateGraph`` config callbacks (never blocks)."""
    try:
        from langchain_core.callbacks import BaseCallbackHandler
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "AegisCallbackHandler needs langchain-core. Install with: "
            "pip install 'aegis-sdk-langgraph[langgraph]'"
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
