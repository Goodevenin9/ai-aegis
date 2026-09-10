"""Persistence contract tests for P2 evidence, knowledge, memory and Agent runs."""

import pytest
import pytest_asyncio

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.security_operations import SecurityOperationsRepository
from aegis.app.services.evidence_processing import EvidenceProcessor


@pytest_asyncio.fixture
async def operations_repo(tmp_path):
    db = DatabaseConnection(tmp_path / "p2.db")
    await run_migrations(db)
    yield SecurityOperationsRepository(db)
    await db.disconnect()


@pytest.mark.asyncio
async def test_evidence_is_deduplicated_and_indexed_with_traceable_chunks(operations_repo):
    evidence = EvidenceProcessor().process("policy.md", b"# Access\nNever read /etc/shadow")

    first = await operations_repo.save_evidence(evidence)
    second = await operations_repo.save_evidence(evidence)
    document = await operations_repo.index_evidence(
        first["evidence_id"], title="Agent policy", document_type="security_policy"
    )
    chunks = await operations_repo.load_chunks(document_types=["security_policy"])

    assert first["evidence_id"] == second["evidence_id"]
    assert len(chunks) == 1
    assert chunks[0].document_id == document["document_id"]
    assert "/etc/shadow" in chunks[0].text


@pytest.mark.asyncio
async def test_confirmed_incident_memory_requires_evidence_and_can_be_deleted(operations_repo):
    with pytest.raises(ValueError, match="confirmed incident memory requires evidence"):
        await operations_repo.save_memory(
            memory_type="incident", subject_key="attack-1", summary="confirmed attack",
            confirmed=True,
        )
    with pytest.raises(ValueError, match="unknown evidence IDs"):
        await operations_repo.save_memory(
            memory_type="incident", subject_key="attack-1", summary="forged",
            confirmed=True, evidence_ids=["ev-does-not-exist"],
        )

    evidence = await operations_repo.save_evidence(
        EvidenceProcessor().process("incident.log", b"blocked outbound request")
    )
    memory = await operations_repo.save_memory(
        memory_type="incident",
        subject_key="attack-1",
        summary="confirmed progressive exfiltration",
        confirmed=True,
        evidence_ids=[evidence["evidence_id"]],
    )

    assert (await operations_repo.list_memories(memory_type="incident"))[0]["confirmed"] is True
    assert await operations_repo.delete_memory(memory["memory_id"]) is True
    assert await operations_repo.list_memories(memory_type="incident") == []


@pytest.mark.asyncio
async def test_agent_run_state_and_node_events_survive_service_restart(operations_repo):
    run = await operations_repo.create_agent_run("incident_investigation", {"query": "analyse"})
    await operations_repo.update_agent_run(
        run["run_id"], status="running", state={"node": "collect_evidence"}
    )
    await operations_repo.append_agent_event(
        run["run_id"], "collect_evidence", "completed", {"evidence_ids": ["evt-1"]}
    )

    restored = await operations_repo.get_agent_run(run["run_id"])

    assert restored["status"] == "running"
    assert restored["state"]["node"] == "collect_evidence"
    assert restored["events"][0]["node_name"] == "collect_evidence"
