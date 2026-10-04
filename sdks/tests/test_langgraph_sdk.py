"""Adapter tests for aegis-sdk-langgraph using a fake langchain stack."""
import asyncio
from types import SimpleNamespace

import aegis_sdk_langgraph as sdk


def _request(name="Bash", args=None, call_id="c1"):
    return SimpleNamespace(tool_call={"name": name, "args": args or {}, "id": call_id})


def test_enforce_blocks(fake_langchain_stack, fake_client):
    fc = fake_client(action="block", reason="danger")
    mw = sdk.secure_middleware(mode="enforce", client=fc)
    out = mw.wrap_tool_call(_request(), lambda req: "RAN")
    assert isinstance(out, fake_langchain_stack.ToolMessage)
    assert fc.audits and fc.audits[0][1]["action"] == "block"


def test_enforce_allows(fake_langchain_stack, fake_client):
    mw = sdk.secure_middleware(mode="enforce", client=fake_client(action="allow"))
    assert mw.wrap_tool_call(_request(), lambda req: "RAN") == "RAN"


def test_runtime_kind_is_langgraph(fake_langchain_stack):
    # the client the middleware builds itself must tag runtime_kind=langgraph
    import aegis_sdk_langgraph as mod

    captured = {}

    class Probe:
        def __init__(self, *a, **k):
            captured["runtime_kind"] = k.get("runtime_kind")

        def evaluate(self, *a, **k):
            import aegis_sdk_core as core

            return core.Verdict(action="allow")

        def audit(self, *a, **k):
            pass

    original = mod.AegisClient
    mod.AegisClient = Probe
    try:
        mod.secure_middleware(mode="observe")
    finally:
        mod.AegisClient = original
    assert captured["runtime_kind"] == "langgraph"


def test_async_path(fake_langchain_stack, fake_client):
    mw = sdk.secure_middleware(mode="enforce", client=fake_client(action="allow"))

    async def handler(req):
        return "RAN"

    assert asyncio.run(mw.awrap_tool_call(_request(), handler)) == "RAN"
