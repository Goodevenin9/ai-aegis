"""Adapter tests for aegis-sdk-langchain using a fake langchain stack."""
import asyncio
from types import SimpleNamespace

import aegis_sdk_langchain as sdk


def _request(name="Bash", args=None, call_id="c1"):
    return SimpleNamespace(tool_call={"name": name, "args": args or {}, "id": call_id})


def test_enforce_blocks_and_returns_toolmessage(fake_langchain_stack, fake_client):
    fc = fake_client(action="block", reason="rm -rf /")
    mw = sdk.secure_middleware(mode="enforce", client=fc)
    ran = {"n": 0}

    def handler(req):
        ran["n"] += 1
        return "RAN"

    out = mw.wrap_tool_call(_request(args={"command": "rm -rf /"}), handler)
    assert isinstance(out, fake_langchain_stack.ToolMessage)
    assert ran["n"] == 0
    assert out.status == "error" and out.tool_call_id == "c1"
    assert "blocked" in out.content
    assert fc.audits and fc.audits[0][1]["action"] == "block"


def test_enforce_allows_and_calls_handler(fake_langchain_stack, fake_client):
    mw = sdk.secure_middleware(mode="enforce", client=fake_client(action="allow"))
    out = mw.wrap_tool_call(_request(), lambda req: "RAN")
    assert out == "RAN"


def test_observe_runs_even_on_block_but_audits(fake_langchain_stack, fake_client):
    fc = fake_client(action="block", reason="would block")
    # add a tiny sleep-free async fake through the same client
    mw = sdk.secure_middleware(mode="observe", client=fc)
    out = mw.wrap_tool_call(_request(), lambda req: "RAN")
    assert out == "RAN"
    assert fc.audits, "non-allow verdict must still be audited in observe mode"


def test_async_path_blocks(fake_langchain_stack, fake_client):
    fc = fake_client(action="block", reason="nope")
    mw = sdk.secure_middleware(mode="enforce", client=fc)

    async def handler(req):
        return "RAN"

    out = asyncio.run(mw.awrap_tool_call(_request(), handler))
    assert isinstance(out, fake_langchain_stack.ToolMessage)


def test_missing_langchain_raises_clear_error(monkeypatch, fake_client):
    import sys

    monkeypatch.setitem(sys.modules, "langchain", None)
    monkeypatch.setitem(sys.modules, "langchain.agents.middleware", None)
    try:
        sdk.secure_middleware(mode="enforce", client=fake_client(action="allow"))
    except ImportError as exc:
        assert "langchain" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ImportError when langchain is absent")


def test_callback_handler_mode_is_observe_only(fake_langchain_stack, fake_client):
    fc = fake_client(action="block")
    handler = sdk.AegisCallbackHandler(client=fc, session_id="s9")
    handler.on_tool_start({"name": "Bash"}, "rm -rf /")
    assert fc.evaluated and fc.evaluated[-1][0] == "Bash"
    assert fc.audits, "observe handler logs non-allow calls"
