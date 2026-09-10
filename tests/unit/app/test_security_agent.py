"""Public workflow tests for the bounded LangGraph security analyst Agent."""

import pytest

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.runtime_policy import RuntimePolicyRepository
from aegis.app.database.repositories.security_operations import SecurityOperationsRepository
from aegis.app.services.evidence_processing import EvidenceProcessor
from aegis.app.services.security_agent import AgentTask, DeterministicAgentModel, SecurityAnalystAgent


@pytest.mark.asyncio
async def test_agent_dynamically_routes_policy_question_to_rag_and_returns_citations(tmp_path):
    db = DatabaseConnection(tmp_path / "agent-rag.db")
    await run_migrations(db)
    repo = SecurityOperationsRepository(db)
    evidence = await repo.save_evidence(
        EvidenceProcessor().process("policy.md", "# 第17条\n禁止读取项目外凭据".encode())
    )
    await repo.index_evidence(
        evidence["evidence_id"], title="企业安全制度", document_type="security_policy"
    )
    agent = SecurityAnalystAgent(repo, model=DeterministicAgentModel())

    result = await agent.start(AgentTask(query="公司哪条制度禁止读取项目外凭据？"))

    assert result["status"] == "completed"
    assert result["state"]["task_type"] == "knowledge_query"
    assert result["result"]["citations"]
    assert result["events"][0]["node_name"] == "route"
    await db.disconnect()


@pytest.mark.asyncio
async def test_policy_change_pauses_for_exact_proposal_approval_then_applies_once(tmp_path):
    db = DatabaseConnection(tmp_path / "agent-approval.db")
    await run_migrations(db)
    operations = SecurityOperationsRepository(db)
    policy = RuntimePolicyRepository(db)
    agent = SecurityAnalystAgent(
        operations,
        model=DeterministicAgentModel(),
        policy_repository=policy,
        evaluator=lambda _variants, **_kwargs: {"five_stage": {"recall": 1.0}},
    )

    waiting = await agent.start(
        AgentTask(
            query="将确认阈值调整为45",
            requested_task="policy_change",
            policy_changes={"confirm_threshold": 45},
        )
    )
    assert waiting["status"] == "awaiting_approval"
    proposal_hash = waiting["approval_hash"]

    completed = await agent.resume(
        waiting["run_id"], decision="approve", proposal_hash=proposal_hash,
        approved_by="security-admin",
    )
    repeated = await agent.resume(
        waiting["run_id"], decision="approve", proposal_hash=proposal_hash,
        approved_by="security-admin",
    )
    with pytest.raises(ValueError, match="proposal hash"):
        await agent.resume(
            waiting["run_id"], decision="approve", proposal_hash="wrong-hash",
            approved_by="security-admin",
        )
    with pytest.raises(ValueError, match="approve decision"):
        await agent.resume(
            waiting["run_id"], decision="reject", proposal_hash=proposal_hash,
            approved_by="security-admin",
        )

    assert completed["status"] == "completed"
    assert (await policy.get_config()).confirm_threshold == 45
    assert repeated["status"] == "completed"
    assert repeated["result"]["idempotent"] is True
    await db.disconnect()


@pytest.mark.asyncio
async def test_agent_failure_is_persisted_and_does_not_touch_runtime_policy(tmp_path):
    class BrokenModel:
        async def run(self, _role, _payload):
            raise TimeoutError("model unavailable")

    db = DatabaseConnection(tmp_path / "agent-failure.db")
    await run_migrations(db)
    operations = SecurityOperationsRepository(db)
    agent = SecurityAnalystAgent(operations, model=BrokenModel())

    result = await agent.start(AgentTask(query="分析这次事件"))

    assert result["status"] == "failed"
    assert "model unavailable" in result["error"]
    await db.disconnect()


@pytest.mark.asyncio
async def test_submit_returns_queued_run_and_completes_in_background(tmp_path):
    db = DatabaseConnection(tmp_path / "agent-background.db")
    await run_migrations(db)
    agent = SecurityAnalystAgent(
        SecurityOperationsRepository(db), model=DeterministicAgentModel()
    )

    queued = await agent.submit(AgentTask(query="解释五段管线"))
    assert queued["status"] == "queued"

    for _ in range(50):
        completed = await agent.inspect(queued["run_id"])
        if completed and completed["status"] not in {"queued", "running"}:
            break
        await __import__("asyncio").sleep(0.01)
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result"]["citations"] == []
    assert "未形成事实性安全结论" in completed["result"]["summary"]
    await db.disconnect()


@pytest.mark.asyncio
async def test_cancellation_persists_and_stops_waiting_model(tmp_path):
    import asyncio
    class WaitingModel:
        async def run(self, role, payload):
            await asyncio.Event().wait()
    db = DatabaseConnection(tmp_path / "cancel.db")
    await run_migrations(db)
    repo = SecurityOperationsRepository(db)
    agent = SecurityAnalystAgent(repo, model=WaitingModel())
    queued = await agent.submit(AgentTask(query="investigate"))
    await asyncio.sleep(0.01)
    stopped = await agent.cancel(queued["run_id"])
    assert stopped["status"] == "cancelled"
    assert (await repo.list_agent_runs())[0]["status"] == "cancelled"
    await db.disconnect()
