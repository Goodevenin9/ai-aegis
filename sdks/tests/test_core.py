"""Behavioural tests for the shared core (no frameworks, no network)."""
import pytest

import aegis_sdk_core as core


def client(responses, runtime="test"):
    c = core.AegisClient(base_url="http://engine.invalid", runtime_kind=runtime, overrides_ttl_s=0)
    calls = []

    def fake_request(path, *, body=None, timeout_s=None):
        calls.append((path, body))
        return responses.get(path, {})

    c._request = fake_request
    c.calls = calls
    return c


# -- normalization / resolution -------------------------------------------

def test_normalize_mcp_decomposes_to_server_tool():
    assert core.normalize_tool_name("mcp__slack__post_message") == ["slack:post_message", "post_message"]


def test_normalize_plain_name_is_itself():
    assert core.normalize_tool_name("my_tool") == ["my_tool"]


@pytest.mark.parametrize("bad", ["", None, 123, "mcp__onlyserver"])
def test_normalize_rejects_junk(bad):
    assert core.normalize_tool_name(bad) == []


def test_resolve_mode_and_base_url(monkeypatch):
    monkeypatch.delenv("AEGIS_SDK_MODE", raising=False)
    monkeypatch.delenv("AEGIS_ENGINE_ENDPOINT", raising=False)
    assert core.resolve_mode() == core.MODE_OBSERVE
    assert core.resolve_mode("enforce") == core.MODE_ENFORCE
    assert core.resolve_mode("garbage") == core.MODE_OBSERVE
    assert core.resolve_base_url() == core.DEFAULT_BASE_URL
    monkeypatch.setenv("AEGIS_ENGINE_ENDPOINT", "https://engine.example/")
    assert core.resolve_base_url() == "https://engine.example"
    assert core.resolve_base_url("http://x:1/") == "http://x:1"


# -- Verdict.decisive ------------------------------------------------------

def _v(action, reachable=True, **kw):
    return core.Verdict(action=action, reachable=reachable, **kw)


def test_observe_always_runs():
    for action in ("allow", "confirm", "block"):
        run, _ = _v(action).decisive(core.MODE_OBSERVE)
        assert run is True


def test_enforce_blocks_only_on_block():
    assert _v("allow").decisive(core.MODE_ENFORCE)[0] is True
    assert _v("confirm").decisive(core.MODE_ENFORCE)[0] is True
    assert _v("block", reason="boom").decisive(core.MODE_ENFORCE)[0] is False


def test_enforce_fail_closed_when_unreachable():
    run, reason = _v("allow", reachable=False).decisive(core.MODE_ENFORCE, fail_closed=True)
    assert run is False and "unreachable" in reason
    run2, _ = _v("allow", reachable=False).decisive(core.MODE_ENFORCE, fail_closed=False)
    assert run2 is True


# -- evaluate() ------------------------------------------------------------

def test_evaluate_deny_override_short_circuits_to_block():
    c = client({
        "/api/tool-permissions/synced-overrides?runtime=test": {
            "synced": [{"tool_id": "Read", "effect": "deny", "reason": "no reads"}]
        },
    })
    v = c.evaluate("Read", {"path": "/x"})
    assert v.action == core.ACTION_BLOCK
    # the pipeline is still consulted and sees the base block
    pipeline_calls = [b for p, b in c.calls if p == "/api/runtime/pretool/decide"]
    assert pipeline_calls and pipeline_calls[0]["base_decision"] == "block"


def test_evaluate_passes_through_pipeline_action():
    c = client({
        "/api/runtime/pretool/decide": {
            "action": "block", "reason": "rm -rf /", "risk_score": 100, "signals": []
        },
    })
    v = c.evaluate("Bash", {"command": "rm -rf /"})
    assert v.action == core.ACTION_BLOCK and v.risk_score == 100 and v.reachable is True


def test_evaluate_fail_open_when_engine_unreachable():
    c = client({})
    v = c.evaluate("Read", {})
    assert v.action == core.ACTION_ALLOW and v.reachable is False


def test_evaluate_headless_escalation_flows_through():
    c = client({
        "/api/runtime/pretool/decide": {
            "action": "block", "reason": "escalated", "headless_escalated": True, "signals": []
        },
    })
    v = c.evaluate("WebFetch", {"url": "http://x"}, headless=True)
    assert v.blocked and v.headless_escalated is True
    body = [b for p, b in c.calls if p == "/api/runtime/pretool/decide"][0]
    assert body["headless"] is True


def test_egress_only_for_network_capable_tools():
    c = client({})
    c.evaluate("Read", {})
    assert not any(p == "/api/egress/evaluate" for p, _ in c.calls)
    c2 = client({})
    c2.evaluate("Bash", {"command": "curl example.com"})
    assert any(p == "/api/egress/evaluate" for p, _ in c2.calls)


# -- audit body ------------------------------------------------------------

def test_audit_body_shape_and_risk_band(monkeypatch):
    c = client({})
    sent = {}

    def capture(path, body):
        sent["path"] = path
        sent["body"] = body

    monkeypatch.setattr(c, "_post_async", capture)
    c.audit("Bash", tool_input={"command": "rm -rf /"}, action="block",
            reason="danger", risk_score=100, session_id="s1",
            pipeline={"action": "block", "risk_score": 100, "layers": {"boundary": {"value": "block"}},
                      "signals": [{"layer": "boundary", "code": "x", "severity": "high", "score": 100}]})
    assert sent["path"] == "/api/tool-permissions/call-audit"
    body = sent["body"]
    assert body["action"] == "block" and body["risk"] == "admin"
    assert body["runtime_kind"] == "test" and body["session_id"] == "s1"
    assert body["tool_id"] == "Bash" and body["args_preview"]
    assert '"schema": "aegis.pretool-pipeline.v1"' in body["reason"]
