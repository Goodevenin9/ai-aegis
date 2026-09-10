"""Persistence contract for session-level intent and drift evidence."""

import pytest

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.runtime_sessions import RuntimeSessionRepository


@pytest.mark.asyncio
async def test_session_state_survives_a_new_repository_instance(tmp_path):
    db = DatabaseConnection(tmp_path / "runtime-sessions.db")
    await run_migrations(db)

    first = RuntimeSessionRepository(db)
    await first.save_state(
        session_key="codex\0session-1",
        runtime_kind="codex",
        session_id="session-1",
        state={
            "drift_score": 55,
            "attempts": {"abc": 2},
            "pending_labels": [],
            "original_intent": "检查项目代码",
            "latest_intent": "读取用户配置",
            "intent_revision": 2,
            "scored_intent_boundary_revision": 0,
            "allowed_capabilities": ["file_read"],
        },
    )

    restored = await RuntimeSessionRepository(db).load_state("codex\0session-1")

    assert restored is not None
    assert restored["drift_score"] == 55
    assert restored["attempts"] == {"abc": 2}
    assert restored["original_intent"] == "检查项目代码"
    await db.disconnect()


@pytest.mark.asyncio
async def test_timeline_is_hash_chained_and_detects_tampering(tmp_path):
    db = DatabaseConnection(tmp_path / "runtime-events.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)

    await repo.append_event(
        session_key="claude-code\0s1",
        runtime_kind="claude-code",
        session_id="s1",
        event_type="llm_input",
        turn_index=1,
        content="读取项目README",
        payload={"source": "user_prompt"},
    )
    await repo.append_event(
        session_key="claude-code\0s1",
        runtime_kind="claude-code",
        session_id="s1",
        event_type="before_tool_call",
        turn_index=1,
        content=None,
        payload={"tool_name": "Read", "drift_score": 0, "action": "allow"},
    )

    timeline = await repo.get_timeline("claude-code\0s1")
    assert [row["event_type"] for row in timeline] == ["llm_input", "before_tool_call"]
    assert timeline[0]["row_hash"] == timeline[1]["prev_hash"]
    assert (await repo.verify_event_chain("claude-code\0s1"))["valid"] is True

    await db.execute(
        "UPDATE runtime_session_events SET payload = ? WHERE seq = 1",
        ('{"source":"tampered"}',),
    )
    integrity = await repo.verify_event_chain("claude-code\0s1")
    assert integrity["valid"] is False
    assert integrity["broken_seq"] == 1
    await db.disconnect()


@pytest.mark.asyncio
async def test_session_summary_exposes_risk_curve_without_raw_secrets(tmp_path):
    db = DatabaseConnection(tmp_path / "runtime-summary.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)
    await repo.save_state(
        session_key="cursor\0s2",
        runtime_kind="cursor",
        session_id="s2",
        state={"drift_score": 90, "original_intent": "审查代码"},
    )
    await repo.append_event(
        session_key="cursor\0s2",
        runtime_kind="cursor",
        session_id="s2",
        event_type="before_tool_call",
        turn_index=2,
        content="api_key:super-secret-value-1234567890",
        payload={"tool_name": "shell", "drift_score": 90, "action": "block"},
    )

    sessions = await repo.list_sessions()
    assert sessions[0]["runtime_kind"] == "cursor"
    assert sessions[0]["drift_score"] == 90
    assert sessions[0]["last_action"] == "block"
    timeline = await repo.get_timeline("cursor\0s2")
    assert "super-secret-value" not in (timeline[0]["content"] or "")
    await db.disconnect()


@pytest.mark.asyncio
async def test_missing_session_is_not_reported_as_an_intact_hash_chain(tmp_path):
    db = DatabaseConnection(tmp_path / "runtime-missing.db")
    await run_migrations(db)
    repo = RuntimeSessionRepository(db)
    integrity = await repo.verify_event_chain("codex\0does-not-exist")
    assert integrity == {
        "valid": False, "broken_seq": None, "checked": 0, "reason": "session_not_found"
    }
    await db.disconnect()
