"""Aegis tool-call security for CrewAI agents.

    from crewai import Agent
    from aegis_sdk_crewai import secure_tools

    agent = Agent(role="Researcher", goal="...", backstory="...",
                  tools=secure_tools(my_tools, mode="enforce"))

CrewAI is not built on langchain-core, so tools are *wrapped* rather than
intercepted by middleware. ``observe`` logs every call; ``enforce`` raises
before the wrapped tool's ``_run`` executes. Decisions are tagged
``runtime_kind="crewai"`` on the shared audit chain.
"""
from __future__ import annotations

import os
from typing import Any, Iterable, Optional, Sequence

from ._core import (  # noqa: F401
    MODE_ENFORCE,
    MODE_OBSERVE,
    AegisClient,
    Verdict,
    resolve_mode,
)

__all__ = ["secure_tools", "install", "AegisClient", "Verdict", "MODE_ENFORCE", "MODE_OBSERVE"]

_RUNTIME_KIND = "crewai"
_ENV_HEADLESS = "AEGIS_HEADLESS"
_TRUTHY = {"1", "true", "yes", "on"}


def _headless() -> bool:
    return str(os.environ.get(_ENV_HEADLESS, "")).strip().lower() in _TRUTHY


def _tool_name(tool: Any) -> str:
    for attr in ("name", "__name__"):
        value = getattr(tool, attr, None)
        if isinstance(value, str) and value:
            return value
    return type(tool).__name__


def _tool_args(args: tuple, kwargs: dict) -> Any:
    if kwargs and args:
        return {"args": list(args), "kwargs": kwargs}
    if kwargs:
        return kwargs
    if len(args) == 1:
        return args[0]
    return list(args)


def guard_call(
    client: AegisClient,
    mode: str,
    fail_closed: bool,
    name: str,
    args: Any,
    session_id: Optional[str],
) -> tuple[bool, str, Verdict]:
    """Shared per-call decision used by both the wrapper and the monkeypatch.

    Returns ``(run, reason, verdict)``; the caller audits on non-allow.
    """
    verdict = client.evaluate(name, args, session_id=session_id, headless=_headless())
    run, reason = verdict.decisive(mode, fail_closed=fail_closed)
    return run, reason, verdict


class _GuardedTool:
    """Duck-typed wrapper: exposes ``name``/``description``/``args_schema`` and
    a guarded ``_run``/``run``/``__call__``."""

    def __init__(
        self,
        inner: Any,
        client: AegisClient,
        mode: str,
        session_id: Optional[str],
        fail_closed: bool,
    ) -> None:
        self._inner = inner
        self._client = client
        self._mode = mode
        self._session_id = session_id
        self._fail_closed = fail_closed
        self.name = _tool_name(inner)
        self.description = getattr(inner, "description", "") or ""
        if hasattr(inner, "args_schema"):
            self.args_schema = inner.args_schema

    def _execute(self, *args: Any, **kwargs: Any) -> Any:
        call_args = _tool_args(args, kwargs)
        run, reason, verdict = guard_call(
            self._client, self._mode, self._fail_closed, self.name, call_args, self._session_id
        )
        if not run:
            self._client.audit(self.name, tool_input=call_args, action="block", reason=reason,
                               session_id=self._session_id, risk_score=verdict.risk_score,
                               pipeline=verdict.raw)
            raise PermissionError(f"Aegis Guard: blocked `{self.name}` — {reason}")
        if verdict.action != "allow":
            self._client.audit(self.name, tool_input=call_args, action=verdict.action,
                               reason=verdict.reason, session_id=self._session_id,
                               risk_score=verdict.risk_score, pipeline=verdict.raw)
        return self._inner._run(*args, **kwargs) if hasattr(self._inner, "_run") else self._inner(*args, **kwargs)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return self._execute(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self._execute(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._execute(*args, **kwargs)


def _make_crewai_tool(inner: Any, client: AegisClient, mode: str,
                      session_id: Optional[str], fail_closed: bool) -> Any:
    """Return a CrewAI ``BaseTool`` subclass instance when crewai is present,
    otherwise the duck-typed wrapper. Lazy so the package imports without crewai."""
    try:
        from crewai.tools import BaseTool  # type: ignore
        from pydantic import PrivateAttr  # type: ignore
    except Exception:
        return _GuardedTool(inner, client, mode, session_id, fail_closed)

    inner_name = _tool_name(inner)
    inner_desc = getattr(inner, "description", "") or ""

    class _CrewAIGuardedTool(BaseTool):
        name: str = inner_name
        description: str = inner_desc
        _inner: Any = PrivateAttr()
        _client: Any = PrivateAttr()
        _mode: str = PrivateAttr()
        _session_id: Any = PrivateAttr()
        _fail_closed: bool = PrivateAttr()

        def __init__(self, **data: Any) -> None:
            data.setdefault("name", inner_name)
            data.setdefault("description", inner_desc)
            super().__init__(**data)
            self._inner = inner
            self._client = client
            self._mode = mode
            self._session_id = session_id
            self._fail_closed = fail_closed

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            call_args = _tool_args(args, kwargs)
            run, reason, verdict = guard_call(
                self._client, self._mode, self._fail_closed, self.name, call_args, self._session_id
            )
            if not run:
                self._client.audit(self.name, tool_input=call_args, action="block", reason=reason,
                                   session_id=self._session_id, risk_score=verdict.risk_score,
                                   pipeline=verdict.raw)
                raise PermissionError(f"Aegis Guard: blocked `{self.name}` — {reason}")
            if verdict.action != "allow":
                self._client.audit(self.name, tool_input=call_args, action=verdict.action,
                                   reason=verdict.reason, session_id=self._session_id,
                                   risk_score=verdict.risk_score, pipeline=verdict.raw)
            return self._inner._run(*args, **kwargs) if hasattr(self._inner, "_run") else self._inner(*args, **kwargs)

    return _CrewAIGuardedTool()


def secure_tools(
    tools: Sequence[Any],
    mode: Optional[str] = None,
    *,
    client: Optional[AegisClient] = None,
    session_id: Optional[str] = None,
    fail_closed: bool = True,
) -> list[Any]:
    """Wrap each tool so Aegis gates it before ``_run`` executes."""
    resolved = resolve_mode(mode)
    cli = client or AegisClient(runtime_kind=_RUNTIME_KIND)
    return [_make_crewai_tool(t, cli, resolved, session_id, fail_closed) for t in tools]


def install(
    mode: Optional[str] = None,
    *,
    client: Optional[AegisClient] = None,
    session_id: Optional[str] = None,
    fail_closed: bool = True,
) -> bool:
    """Best-effort global guard: monkeypatch ``crewai.tools.BaseTool.run``.

    Patches the *public* ``run`` entry point, not ``_run`` — CrewAI tools
    routinely override ``_run``, which would shadow a ``_run`` patch entirely.
    Returns ``True`` when the patch was applied, ``False`` when crewai is not
    importable. Prefer :func:`secure_tools` when you can wrap explicitly; do
    not combine both (the wrapped tool's ``_run`` would be guarded twice).
    """
    resolved = resolve_mode(mode)
    cli = client or AegisClient(runtime_kind=_RUNTIME_KIND)
    try:
        from crewai.tools import BaseTool  # type: ignore
    except Exception:
        return False

    if getattr(BaseTool, "_aegis_patched", False):
        return True
    original = BaseTool.run

    def _guarded_run(self: Any, *args: Any, **kwargs: Any) -> Any:
        call_args = _tool_args(args, kwargs)
        name = _tool_name(self)
        run, reason, verdict = guard_call(cli, resolved, fail_closed, name, call_args, session_id)
        if not run:
            cli.audit(name, tool_input=call_args, action="block", reason=reason,
                      session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
            raise PermissionError(f"Aegis Guard: blocked `{name}` — {reason}")
        if verdict.action != "allow":
            cli.audit(name, tool_input=call_args, action=verdict.action, reason=verdict.reason,
                      session_id=session_id, risk_score=verdict.risk_score, pipeline=verdict.raw)
        return original(self, *args, **kwargs)

    BaseTool.run = _guarded_run
    BaseTool._aegis_patched = True
    return True
