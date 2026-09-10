"""P2 Security Operations API: evidence, RAG, memory and bounded Agent runs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.repositories.runtime_policy import RuntimePolicyRepository
from aegis.app.database.repositories.runtime_sessions import RuntimeSessionRepository
from aegis.app.database.repositories.security_operations import SecurityOperationsRepository
from aegis.app.services.evidence_processing import EvidenceProcessor
from aegis.app.services.security_agent import AgentTask, SecurityAnalystAgent
from aegis.app.services.security_rag import SecurityRAG
from aegis.app.services.agent_delivery import export_run, load_external_results
from aegis.app.services.security_agent import DeepSeekAgentModel

router = APIRouter(prefix="/security-operations")
_repository: Optional[SecurityOperationsRepository] = None
_agent: Optional[SecurityAnalystAgent] = None
_processor = EvidenceProcessor()
_rag = SecurityRAG()


def configure_security_operations(db: DatabaseConnection) -> None:
    global _repository, _agent
    _repository = SecurityOperationsRepository(db)
    try:
        _agent = SecurityAnalystAgent(
            _repository,
            runtime_sessions=RuntimeSessionRepository(db),
            policy_repository=RuntimePolicyRepository(db),
        )
    except RuntimeError as exc:
        if "requires the app extra" not in str(exc):
            raise
        # Base/Python 3.9 installs can still use evidence, RAG and memory;
        # the LangGraph Agent endpoint reports 503 until the app extra runs
        # under Python 3.10+.
        _agent = None


def _require_repository() -> SecurityOperationsRepository:
    if not _repository:
        raise HTTPException(status_code=503, detail="security operations persistence unavailable")
    return _repository


def _require_agent() -> SecurityAnalystAgent:
    if not _agent:
        raise HTTPException(status_code=503, detail="security Agent unavailable")
    return _agent


def _require_ui(token: Optional[str]) -> None:
    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(token)


class IndexEvidenceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    document_type: Literal["security_policy", "incident", "rule", "security_knowledge"]
    policy_version: Optional[str] = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    document_types: list[str] = Field(default_factory=list, max_length=16)
    limit: int = Field(default=5, ge=1, le=20)


class RAGEvaluationCase(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    relevant_chunk_ids: list[str] = Field(..., min_length=1, max_length=50)


class RAGEvaluationRequest(BaseModel):
    cases: list[RAGEvaluationCase] = Field(..., min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class MemoryCreateRequest(BaseModel):
    memory_type: Literal["workflow", "session", "incident", "preference"]
    subject_key: str = Field(..., min_length=1, max_length=256)
    summary: str = Field(..., min_length=1, max_length=8000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=128)
    confirmed: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ttl_days: Optional[int] = Field(default=None, ge=1, le=3650)


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    requested_task: Literal[
        "auto", "general_explanation", "knowledge_query", "incident_investigation",
        "evidence_analysis", "dataset_evaluation", "policy_change",
    ] = "auto"
    evidence_ids: list[str] = Field(default_factory=list, max_length=128)
    session_keys: list[str] = Field(default_factory=list, max_length=32)
    document_types: list[str] = Field(default_factory=list, max_length=16)
    policy_changes: dict[str, int] = Field(default_factory=dict)


class AgentResumeRequest(BaseModel):
    decision: Literal["approve", "reject"]
    proposal_hash: str = Field(..., min_length=64, max_length=64)
    approved_by: str = Field(..., min_length=1, max_length=200)


@router.post("/evidence/upload", status_code=201)
async def upload_evidence(
    file: UploadFile = File(...),
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    data = await file.read(_processor.max_bytes + 1)
    try:
        processed = _processor.process(file.filename or "evidence", data, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await _require_repository().save_evidence(processed)


@router.get("/evidence")
async def list_evidence(limit: int = 100) -> dict[str, Any]:
    items = await _require_repository().list_evidence(limit)
    for item in items:
        text = item.pop("text_content", "") or ""
        item["text_preview"] = text[:500]
    return {"evidence": items, "total": len(items)}


@router.post("/evidence/{evidence_id}/index", status_code=201)
async def index_evidence(
    evidence_id: str,
    request: IndexEvidenceRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    try:
        return await _require_repository().index_evidence(
            evidence_id,
            title=request.title,
            document_type=request.document_type,
            policy_version=request.policy_version,
            metadata=request.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc


@router.post("/rag/search")
async def search_knowledge(request: RAGSearchRequest) -> dict[str, Any]:
    chunks = await _require_repository().load_chunks(
        document_types=request.document_types or None
    )
    results = _rag.search(request.query, chunks, limit=request.limit)
    return {"results": [asdict(result) for result in results], "total": len(results)}


@router.post("/rag/evaluate")
async def evaluate_knowledge(request: RAGEvaluationRequest) -> dict[str, Any]:
    chunks = await _require_repository().load_chunks()
    return _rag.evaluate([case.model_dump() for case in request.cases], chunks, k=request.k)


@router.post("/memories", status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    try:
        return await _require_repository().save_memory(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memories")
async def list_memories(
    memory_type: Optional[str] = None,
    subject_key: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    items = await _require_repository().list_memories(
        memory_type=memory_type, subject_key=subject_key, limit=limit
    )
    return {"memories": items, "total": len(items)}


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    if not await _require_repository().delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="memory not found")
    return {"deleted": True, "memory_id": memory_id}


@router.post("/agent/runs", status_code=202)
async def start_agent_run(
    request: AgentRunRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    return await _require_agent().submit(
        AgentTask(
            query=request.query,
            requested_task=request.requested_task,
            evidence_ids=tuple(request.evidence_ids),
            session_keys=tuple(request.session_keys),
            document_types=tuple(request.document_types),
            policy_changes=request.policy_changes,
        )
    )


@router.get("/agent/model")
async def agent_model_status() -> dict[str, Any]:
    model = _require_agent().model
    primary = getattr(model, "primary", model)
    if isinstance(primary, DeepSeekAgentModel):
        return primary.status()
    return {"configured": False, "connection_status": "offline", "model": "deterministic"}


@router.get("/agent/tools")
async def agent_tool_catalog() -> dict[str, Any]:
    return {"tools": _require_agent().tools.catalog()}


@router.post("/agent/model/test")
async def test_agent_model(x_aegis_ui_token: Optional[str] = Header(None)) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    model = _require_agent().model
    primary = getattr(model, "primary", model)
    if not isinstance(primary, DeepSeekAgentModel):
        raise HTTPException(status_code=503, detail="No language model configured")
    try:
        await primary.run("task_router", {"query": "检索安全制度", "allowed_tasks": ["knowledge_query"]})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Model connection failed: {type(exc).__name__}") from exc
    return primary.status()


@router.get("/benchmarks")
async def benchmark_results() -> dict[str, Any]:
    return load_external_results()


@router.get("/agent/runs/{run_id}/export")
async def export_agent_run(
    run_id: str,
    format: Literal["markdown", "json"] = "markdown",
    x_aegis_ui_token: Optional[str] = Header(None),
) -> Response:
    _require_ui(x_aegis_ui_token)
    run = await _require_agent().inspect(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    extension = "md" if format == "markdown" else "json"
    return Response(export_run(run, format), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="aegis-report.{extension}"'})


@router.get("/agent/runs/{run_id}")
async def inspect_agent_run(run_id: str) -> dict[str, Any]:
    result = await _require_agent().inspect(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return result


@router.get("/agent/runs")
async def list_agent_runs() -> dict[str, Any]:
    return {"runs": await _require_repository().list_agent_runs()}


@router.post("/agent/runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str, x_aegis_ui_token: Optional[str] = Header(None)) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    try:
        return await _require_agent().cancel(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc


@router.post("/agent/runs/{run_id}/resume")
async def resume_agent_run(
    run_id: str,
    request: AgentResumeRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    _require_ui(x_aegis_ui_token)
    try:
        return await _require_agent().resume(run_id, **request.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = ["configure_security_operations", "router"]
