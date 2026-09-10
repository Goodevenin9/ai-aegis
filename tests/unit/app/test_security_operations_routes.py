"""API seam tests for the P2 Security Operations surface."""

from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.server.routes import security_operations
from aegis.app.server.routes.jit_access import _UI_TOKEN


@pytest.mark.asyncio
async def test_upload_index_search_and_memory_endpoints_form_one_vertical_slice(tmp_path):
    db = DatabaseConnection(tmp_path / "operations-routes.db")
    await run_migrations(db)
    security_operations.configure_security_operations(db)
    upload = UploadFile(
        BytesIO("# 第17条\n禁止读取项目外凭据".encode()),
        filename="policy.md",
        headers=Headers({"content-type": "text/markdown"}),
    )

    evidence = await security_operations.upload_evidence(upload, _UI_TOKEN)
    document = await security_operations.index_evidence(
        evidence["evidence_id"],
        security_operations.IndexEvidenceRequest(
            title="企业制度", document_type="security_policy"
        ),
        _UI_TOKEN,
    )
    search = await security_operations.search_knowledge(
        security_operations.RAGSearchRequest(query="哪条制度禁止读取项目外凭据")
    )
    memory = await security_operations.create_memory(
        security_operations.MemoryCreateRequest(
            memory_type="preference",
            subject_key="report-language",
            summary="使用中文报告",
            confirmed=True,
        ),
        _UI_TOKEN,
    )

    assert document["chunk_count"] == 1
    assert search["results"][0]["citation"].startswith("企业制度")
    assert memory["memory_type"] == "preference"
    await db.disconnect()
