"""P1 contracts for manifests, configuration, and bounded trust reuse."""

import pytest
from fastapi import HTTPException

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.runtime_policy import RuntimePolicyRepository
from aegis.app.server.routes import runtime_pipeline
from aegis.app.server.routes import jit_access
from aegis.app.services.pretool_pipeline import SessionDriftStore


@pytest.mark.asyncio
async def test_manifest_drives_pretool_capability_when_adapter_does_not_supply_one(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "p1-policy.db")
    assert await run_migrations(db) == 47
    repo = RuntimePolicyRepository(db)
    await repo.save_manifest("codex", "default", ["file_read", "shell_exec"], str(tmp_path), "dev")
    monkeypatch.setattr(runtime_pipeline, "_policy_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    decision = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash",
            tool_input={"command": "pytest"},
            session_id="manifested",
            runtime_kind="codex",
        )
    )

    assert decision["action"] == "allow"
    assert decision["policy"]["manifest_id"] == "default"
    await db.disconnect()


@pytest.mark.asyncio
async def test_pipeline_config_is_persisted_and_applied(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "p1-config.db")
    await run_migrations(db)
    repo = RuntimePolicyRepository(db)
    monkeypatch.setattr(runtime_pipeline, "_policy_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())
    token = (await jit_access.get_ui_token())["token"]
    with pytest.raises(HTTPException) as denied:
        await runtime_pipeline.update_pipeline_config(
            runtime_pipeline.PipelineConfigRequest(confirm_threshold=20, block_threshold=60),
            x_aegis_ui_token=None,
        )
    assert getattr(denied.value, "status_code", None) == 403
    saved = await runtime_pipeline.update_pipeline_config(
        runtime_pipeline.PipelineConfigRequest(confirm_threshold=20, block_threshold=60),
        x_aegis_ui_token=token,
    )

    assert saved["version"] == 1
    assert (await runtime_pipeline.get_pipeline_config())["config"]["confirm_threshold"] == 20
    await db.disconnect()


@pytest.mark.asyncio
async def test_short_term_trust_reuses_only_the_approved_capability(monkeypatch):
    monkeypatch.setattr(runtime_pipeline, "_policy_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())
    await runtime_pipeline.grant_session_trust(
        runtime_pipeline.TrustGrantRequest(
            session_id="trusted", runtime_kind="codex", capability="shell_exec", max_uses=1
        ),
        x_aegis_ui_token=(await jit_access.get_ui_token())["token"],
    )

    first = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash", tool_input={"command": "git status"},
            session_id="trusted", runtime_kind="codex",
        )
    )
    second = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash", tool_input={"command": "git status"},
            session_id="trusted", runtime_kind="codex",
        )
    )

    assert first["action"] == "allow"
    assert first["policy"]["trusted_capabilities_reused"] == ["shell_exec"]
    assert second["action"] == "confirm"


@pytest.mark.asyncio
async def test_short_term_trust_requires_local_ui_approval_token(monkeypatch):
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())

    with pytest.raises(HTTPException) as exc:
        await runtime_pipeline.grant_session_trust(
            runtime_pipeline.TrustGrantRequest(
                session_id="agent", runtime_kind="codex", capability="shell_exec"
            ),
            x_aegis_ui_token=None,
        )
    assert getattr(exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_unrelated_tool_does_not_consume_trusted_shell_grant(monkeypatch):
    store = SessionDriftStore()
    monkeypatch.setattr(runtime_pipeline, "_policy_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", store)
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())
    store.grant_trust("codex\0agent", "shell_exec", max_uses=1)

    await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Read", tool_input={"file_path": "README.md"},
            session_id="agent", runtime_kind="codex",
        )
    )
    shell = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash", tool_input={"command": "git status"},
            session_id="agent", runtime_kind="codex",
        )
    )

    assert shell["action"] == "allow"
    assert shell["policy"]["trusted_capabilities_reused"] == ["shell_exec"]


@pytest.mark.asyncio
async def test_session_manifest_is_authoritative_over_adapter_self_report(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "p1-session-manifest.db")
    await run_migrations(db)
    repo = RuntimePolicyRepository(db)
    await repo.save_manifest(
        "codex", "default", ["file_read"], str(tmp_path), "read only", "session-1"
    )
    monkeypatch.setattr(runtime_pipeline, "_policy_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_repository", None)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    decision = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash", tool_input={"command": "git status"},
            session_id="session-1", runtime_kind="codex",
            allowed_capabilities=["shell_exec"],
        )
    )

    assert decision["action"] == "confirm"
    assert decision["policy"]["manifest_id"] == "default"
    await db.disconnect()


@pytest.mark.asyncio
async def test_manifest_rejects_unknown_capability(tmp_path):
    db = DatabaseConnection(tmp_path / "p1-invalid.db")
    await run_migrations(db)
    repo = RuntimePolicyRepository(db)
    with pytest.raises(ValueError, match="unknown capabilities"):
        await repo.save_manifest("codex", "default", ["become_admin"], None, "")
    await db.disconnect()
