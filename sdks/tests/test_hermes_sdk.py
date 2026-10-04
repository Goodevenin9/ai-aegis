"""Adapter tests for aegis-sdk-hermes: guard, MCP candidates, builtins drift."""
import ast
import sys
from pathlib import Path

import aegis_sdk_hermes as sdk
from aegis_sdk_hermes import tool_id
from aegis_sdk_hermes.plugin import AegisGuard

ROOT = Path(__file__).resolve().parents[1]
APP_TABLE = ROOT.parent / "src" / "aegis" / "app" / "server" / "routes" / "tool_permissions.py"


def test_enforce_returns_block_directive(fake_client):
    guard = AegisGuard(mode="enforce", client=fake_client(action="block", reason="danger"))
    directive = guard.pre_tool_call(tool_name="terminal", args={"command": "rm -rf /"})
    assert directive == {"action": "block", "message": "Aegis Guard: danger"}


def test_register_wires_pre_tool_call_hook(fake_client):
    calls = {}

    class Ctx:
        def register_hook(self, name, cb):
            calls["name"] = name
            calls["cb"] = cb

    guard = sdk.plugin.register(Ctx())
    assert calls["name"] == "pre_tool_call"
    # bound method of a guard; invoke the Hermes-style keyword call
    assert callable(calls["cb"])
    assert isinstance(guard, AegisGuard)


def test_observe_never_blocks(fake_client):
    guard = AegisGuard(mode="observe", client=fake_client(action="block"))
    assert guard.pre_tool_call("terminal", {"command": "rm -rf /"}) is None


def test_allow_returns_none(fake_client):
    guard = AegisGuard(mode="enforce", client=fake_client(action="allow"))
    assert guard.pre_tool_call("read_file", {"path": "/x"}) is None


def test_evaluate_receives_mcp_candidates(fake_client):
    fc = fake_client(action="allow")
    guard = AegisGuard(mode="observe", client=fc)
    guard.pre_tool_call("mcp_slack_post_message", {"text": "hi"})
    _, _, kwargs = fc.evaluated[-1]
    cands = kwargs.get("candidates")
    assert cands and "mcp_slack_post_message" in cands and "slack:post_message" in cands


def test_resolve_candidates_shapes():
    assert sdk.resolve_candidates("terminal") == ["terminal"]
    cands = sdk.resolve_candidates("mcp_slack_post_message")
    assert cands[0] == "mcp_slack_post_message"
    assert "slack:post_message" in cands
    assert sdk.resolve_candidates("") == []


def test_builtins_union_matches_app_table():
    tree = ast.parse(APP_TABLE.read_text(encoding="utf-8"))
    app_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "HERMES_BUILTINS":
            for elt in node.value.elts:
                app_names.add(elt.elts[0].value)
    assert app_names, "could not parse the app-side HERMES_BUILTINS"
    assert set(tool_id.HERMES_BUILTINS) == app_names, (
        f"only in SDK: {sorted(set(tool_id.HERMES_BUILTINS) - app_names)}; "
        f"only in app: {sorted(app_names - set(tool_id.HERMES_BUILTINS))}"
    )
    assert len(tool_id.HERMES_BUILTINS) == len(set(tool_id.HERMES_BUILTINS))


def test_install_without_hermes_agent_still_returns_guard(fake_client):
    guard = sdk.install(mode="observe", client=fake_client(action="allow"))
    assert isinstance(guard, AegisGuard)


def test_entry_point_target_is_importable():
    # the pyproject entry point references aegis_sdk_hermes.plugin:register
    from aegis_sdk_hermes import plugin as plugin_mod

    assert callable(plugin_mod.register)
