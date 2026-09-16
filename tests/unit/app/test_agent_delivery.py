"""Delivery contracts: credentials, routing, persisted evidence and model isolation."""
import json

import pytest
from fastapi import HTTPException

from aegis.app.services.agent_delivery import read_model_key, load_external_results, export_run
from aegis.app.services.semantic_evidence import parse_intent_evidence
from aegis.app.services.pretool_pipeline import (
    SessionDriftStore, PreToolContext, run_pretool_pipeline,
)
from aegis.app.services.security_agent import DeepSeekAgentModel
from aegis.app.server.routes import security_operations
from aegis.app.server.routes.jit_access import _UI_TOKEN
from aegis.app.server.routes.security_operations import start_agent_run, AgentRunRequest
from aegis.app.services.agent_tools import SecurityToolRegistry, EvidenceArgs


def test_key_file_is_server_only_and_status_does_not_reveal_it(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    path = tmp_path / "key"
    path.write_text("synthetic-private-value", encoding="utf-8")
    monkeypatch.setenv("AEGIS_DEEPSEEK_API_KEY_FILE", str(path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "stale-unrelated-key")
    assert read_model_key() == "synthetic-private-value"
    status = DeepSeekAgentModel().status()
    assert status["configured"] is True
    assert status["connection_status"] == "untested"
    assert "synthetic-private-value" not in json.dumps(status)


def test_report_is_loaded_with_hash_and_missing_report_is_not_fabricated(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    monkeypatch.setenv("AEGIS_BENCHMARK_REPORT", str(path))
    assert load_external_results()["status"] == "unavailable"
    path.write_text(json.dumps({"benchmarks": [], "run_metadata": {"model": "test"}}))
    result = load_external_results()
    assert result["status"] == "available"
    assert len(result["report_sha256"]) == 64
    assert result["run_metadata"]["model"] == "test"


@pytest.mark.asyncio
async def test_model_cannot_be_spent_by_an_unauthenticated_agent_request():
    with pytest.raises(HTTPException) as error:
        await start_agent_run(AgentRunRequest(query="hello"), None)
    assert error.value.status_code == 403


def test_explicit_harm_survives_checkpoint_and_requires_repetition_for_review():
    evidence = parse_intent_evidence(json.dumps({
        "theme_shifted": False, "permission_probing": False, "request_escalation": False,
        "explicit_harm": True, "requested_capabilities": [], "requested_radius": "none",
    }))
    store = SessionDriftStore()
    store.observe_intent_evidence("session", evidence)
    checkpoint = store.snapshot("session")
    restored = SessionDriftStore()
    restored.restore("session", checkpoint)
    decision = run_pretool_pipeline(PreToolContext(
        tool_name="Read", tool_input={"file_path": "README.md"}, session_id="session",
        runtime_kind="test", allowed_capabilities=frozenset({"file_read"}),
    ), restored)
    assert decision.action == "allow"
    assert any(s.code == "drift.explicit_harm" for s in decision.signals)
    restored.observe_intent_evidence("session", evidence)
    repeated = run_pretool_pipeline(PreToolContext(
        tool_name="Read", tool_input={"file_path": "README.md"}, session_id="session",
        runtime_kind="test", allowed_capabilities=frozenset({"file_read"}),
    ), restored)
    assert repeated.action == "confirm"


def test_explicit_harm_rejects_string_booleans():
    with pytest.raises(ValueError):
        parse_intent_evidence(json.dumps({
            "theme_shifted": False, "permission_probing": False, "request_escalation": False,
            "explicit_harm": "false", "requested_capabilities": [], "requested_radius": "none",
        }))


def test_markdown_export_contains_report_id_and_evidence():
    value = export_run({"run_id": "run-test", "status": "completed", "events": [],
                        "result": {"summary": "调查结果", "citations": ["ev-1"]}})
    assert "run-test" in value and "ev-1" in value and "调查结果" in value


@pytest.mark.asyncio
async def test_tool_registry_validates_arguments_and_rejects_arbitrary_tools():
    registry = SecurityToolRegistry()
    called = []
    async def read(evidence_id):
        called.append(evidence_id)
        return {"id": evidence_id}
    registry.register("get_evidence", EvidenceArgs, read)
    assert await registry.execute("get_evidence", {"evidence_id": "ev-1"}) == {"id": "ev-1"}
    with pytest.raises(ValueError):
        await registry.execute("shell", {"command": "example"})
    with pytest.raises(ValueError):
        await registry.execute("get_evidence", {"evidence_id": "ev-2", "command": "example"})
    assert called == ["ev-1"]


@pytest.mark.asyncio
async def test_agent_export_requires_local_ui_token(monkeypatch):
    class Agent:
        async def inspect(self, _run_id):
            return {"run_id": "run-1", "status": "completed", "result": {}}

    monkeypatch.setattr(security_operations, "_agent", Agent())
    with pytest.raises(HTTPException) as denied:
        await security_operations.export_agent_run("run-1", "markdown", None)
    assert denied.value.status_code == 403

    response = await security_operations.export_agent_run("run-1", "markdown", _UI_TOKEN)
    assert response.headers["content-disposition"].endswith('aegis-report.md"')
