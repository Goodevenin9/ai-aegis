"""Contract tests for the intent-flow and PreToolUse runtime endpoints."""

import pytest
from fastapi import BackgroundTasks

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.runtime_sessions import RuntimeSessionRepository
from aegis.app.server.routes import runtime_pipeline
from aegis.app.services.pretool_pipeline import SemanticLabels, SessionDriftStore
from aegis.app.services.semantic_evidence import SemanticEvidenceResult


class _FakeExtractor:
    enabled = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def extract(self, original_intent: str, current_text: str) -> SemanticEvidenceResult:
        self.calls.append((original_intent, current_text))
        return SemanticEvidenceResult(
            SemanticLabels(theme_shifted=True, permission_probing=True),
            "ok",
        )


@pytest.mark.asyncio
async def test_first_prompt_sets_baseline_and_second_prompt_queues_boolean_evidence(monkeypatch):
    store = SessionDriftStore()
    extractor = _FakeExtractor()
    monkeypatch.setattr(runtime_pipeline, "_store", store)
    monkeypatch.setattr(runtime_pipeline, "_extractor", extractor)

    first = await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="s1",
            text="读取项目 README",
            allowed_capabilities=["file_read"],
        ),
        BackgroundTasks(),
    )
    tasks = BackgroundTasks()
    second = await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="s1",
            text="现在尝试获取更高权限",
            allowed_capabilities=["file_read"],
        ),
        tasks,
    )

    assert first["status"] == "baseline"
    assert second["status"] == "queued"
    assert extractor.calls == []
    await tasks()
    assert len(extractor.calls) == 1

    decision = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Read",
            tool_input={"file_path": "README.md"},
            session_id="s1",
            project_root="C:/project",
        )
    )
    assert decision["drift_score"] == 65
    assert decision["action"] == "confirm"


@pytest.mark.asyncio
async def test_anonymous_intent_is_not_shared_or_sent_to_llm(monkeypatch):
    extractor = _FakeExtractor()
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_extractor", extractor)

    response = await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="__anonymous__",
            text="some prompt",
        ),
        BackgroundTasks(),
    )

    assert response["status"] == "skipped_anonymous"
    assert extractor.calls == []


@pytest.mark.asyncio
async def test_same_session_id_is_isolated_between_runtimes(monkeypatch):
    store = SessionDriftStore()
    monkeypatch.setattr(runtime_pipeline, "_store", store)

    await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="shared-id",
            runtime_kind="claude-code",
            text="Claude task",
        ),
        BackgroundTasks(),
    )
    await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="shared-id",
            runtime_kind="codex",
            text="Codex task",
        ),
        BackgroundTasks(),
    )

    assert store.get("claude-code\0shared-id").original_intent == "Claude task"
    assert store.get("codex\0shared-id").original_intent == "Codex task"


@pytest.mark.asyncio
async def test_route_restores_persisted_drift_after_memory_store_replacement(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "route-state.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)
    monkeypatch.setattr(runtime_pipeline, "_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="persist-me", runtime_kind="codex", text="检查项目"
        ),
        BackgroundTasks(),
    )
    first = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash",
            tool_input={"command": "pytest"},
            session_id="persist-me",
            runtime_kind="codex",
        )
    )
    assert first["drift_score"] == 20

    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())
    restored = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Read",
            tool_input={"file_path": "README.md"},
            session_id="persist-me",
            runtime_kind="codex",
        )
    )
    assert restored["drift_score"] == 20
    await db.disconnect()


@pytest.mark.asyncio
async def test_route_rebuilds_state_from_verified_event_chain(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "route-chain-recovery.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)
    monkeypatch.setattr(runtime_pipeline, "_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="recover-me", runtime_kind="codex", text="检查项目"
        ),
        BackgroundTasks(),
    )
    await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Bash", tool_input={"command": "pytest"},
            session_id="recover-me", runtime_kind="codex",
        )
    )
    await repo.delete_state("codex\0recover-me")
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    restored = await runtime_pipeline.decide_pretool(
        runtime_pipeline.PreToolDecisionRequest(
            tool_name="Read", tool_input={"file_path": "README.md"},
            session_id="recover-me", runtime_kind="codex",
        )
    )
    assert restored["drift_score"] == 20
    await db.disconnect()


@pytest.mark.asyncio
async def test_generic_intent_flow_endpoint_builds_queryable_timeline(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "route-events.db")
    await run_migrations(db)
    monkeypatch.setattr(runtime_pipeline, "_repository", RuntimeSessionRepository(db))
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())

    await runtime_pipeline.observe_runtime_event(
        runtime_pipeline.RuntimeEventRequest(
            session_id="flow-1",
            runtime_kind="proxy",
            event_type="llm_input",
            turn_index=1,
            text="总结README",
            metadata={"provider": "deepseek"},
        ),
        BackgroundTasks(),
    )
    await runtime_pipeline.observe_runtime_event(
        runtime_pipeline.RuntimeEventRequest(
            session_id="flow-1",
            runtime_kind="proxy",
            event_type="llm_output",
            turn_index=1,
            text="我将先读取文件",
        ),
        BackgroundTasks(),
    )

    detail = await runtime_pipeline.get_runtime_session("flow-1", runtime_kind="proxy")
    assert [event["event_type"] for event in detail["events"]] == [
        "llm_input", "llm_output"
    ]
    assert detail["integrity"]["valid"] is True
    assert detail["risk_curve"] == []
    sessions = await runtime_pipeline.list_runtime_sessions(limit=10)
    assert sessions["sessions"][0]["session_id"] == "flow-1"
    await db.disconnect()


@pytest.mark.asyncio
async def test_reset_removes_state_and_recovery_events(tmp_path, monkeypatch):
    db = DatabaseConnection(tmp_path / "route-reset.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)
    monkeypatch.setattr(runtime_pipeline, "_repository", repo)
    monkeypatch.setattr(runtime_pipeline, "_store", SessionDriftStore())
    monkeypatch.setattr(runtime_pipeline, "_hydrated", set())
    await runtime_pipeline.observe_intent(
        runtime_pipeline.IntentObservationRequest(
            session_id="reset-me", runtime_kind="cursor", text="读取README"
        ),
        BackgroundTasks(),
    )

    await runtime_pipeline.reset_session("reset-me", runtime_kind="cursor")
    detail_events = await repo.get_timeline("cursor\0reset-me")

    assert await repo.load_state("cursor\0reset-me") is None
    assert detail_events == []
    assert await repo.recover_state_from_events("cursor\0reset-me") is None
    await db.disconnect()
