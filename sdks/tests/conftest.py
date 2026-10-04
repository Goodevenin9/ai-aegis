"""Make every SDK package importable, and provide a fake langchain stack.

The SDK packages deliberately import their framework lazily, so the adapter
tests inject lightweight fakes for ``langchain`` / ``langchain_core`` instead
of depending on the real frameworks being installed.
"""
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]

for extra in (ROOT / "_core",):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
for pkg in sorted(ROOT.glob("aegis-sdk-*")):
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))


@pytest.fixture
def fake_langchain_stack(monkeypatch):
    """Install minimal ``langchain``/``langchain_core`` fakes into sys.modules."""

    class AgentMiddleware:  # base class the SDK subclasses
        pass

    class ToolMessage:
        def __init__(self, content, tool_call_id=None, status=None):
            self.content = content
            self.tool_call_id = tool_call_id
            self.status = status

    class BaseCallbackHandler:
        def __init__(self, *args, **kwargs):
            pass

    def mod(name):
        return types.ModuleType(name)

    langchain = mod("langchain")
    agents = mod("langchain.agents")
    middleware = mod("langchain.agents.middleware")
    middleware.AgentMiddleware = AgentMiddleware
    agents.middleware = middleware
    langchain.agents = agents

    langchain_core = mod("langchain_core")
    messages = mod("langchain_core.messages")
    messages.ToolMessage = ToolMessage
    callbacks = mod("langchain_core.callbacks")
    callbacks.BaseCallbackHandler = BaseCallbackHandler
    langchain_core.messages = messages
    langchain_core.callbacks = callbacks

    for name, module in {
        "langchain": langchain,
        "langchain.agents": agents,
        "langchain.agents.middleware": middleware,
        "langchain_core": langchain_core,
        "langchain_core.messages": messages,
        "langchain_core.callbacks": callbacks,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    return SimpleNamespace(AgentMiddleware=AgentMiddleware, ToolMessage=ToolMessage,
                           BaseCallbackHandler=BaseCallbackHandler)


@pytest.fixture
def fake_client():
    """A configurable stand-in for AegisClient that records audits."""
    import aegis_sdk_core as core

    class FakeClient:
        def __init__(self, action="allow", reachable=True, reason=None):
            self.verdict = core.Verdict(action=action, reachable=reachable, reason=reason)
            self.audits = []
            self.evaluated = []

        def evaluate(self, name, args=None, **kwargs):
            self.evaluated.append((name, args, kwargs))
            return self.verdict

        def audit(self, name, **kwargs):
            self.audits.append((name, kwargs))

    return FakeClient
