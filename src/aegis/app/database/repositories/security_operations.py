"""Unified persistence seam for P2 evidence, RAG, memory and Agent workflows."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence

from aegis.app.database.connection import DatabaseConnection
from aegis.app.services.evidence_processing import ProcessedEvidence
from aegis.app.services.security_rag import SecurityChunk, chunk_security_document
from aegis.app.utils.redaction import redact_secrets


def _safe(value: Any) -> Any:
    if isinstance(value, str):
        redacted, _ = redact_secrets(value, direction="incoming")
        return str(redacted)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe(str(value))


class SecurityOperationsRepository:
    """Small public API over all durable P2 local-first state."""

    MEMORY_TYPES = frozenset({"workflow", "session", "incident", "preference"})

    def __init__(self, db: DatabaseConnection, tenant_id: str = "local") -> None:
        self.db = db
        self.tenant_id = tenant_id.strip() or "local"

    async def save_evidence(self, evidence: ProcessedEvidence) -> dict[str, Any]:
        existing = await self.db.fetch_one(
            "SELECT evidence_id FROM security_evidence WHERE tenant_id = ? AND content_hash = ?",
            (self.tenant_id, evidence.content_hash),
        )
        if existing:
            result = await self.get_evidence(existing["evidence_id"])
            if result is not None:
                return result
        evidence_id = f"ev-{uuid.uuid4().hex}"
        await self.db.execute(
            """
            INSERT INTO security_evidence (
                evidence_id, tenant_id, evidence_type, source_name, media_type,
                content_hash, text_content, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                self.tenant_id,
                evidence.evidence_type,
                evidence.source_name,
                evidence.media_type,
                evidence.content_hash,
                evidence.text,
                json.dumps(_safe(evidence.metadata), ensure_ascii=False, sort_keys=True),
            ),
        )
        result = await self.get_evidence(evidence_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("created evidence could not be loaded")
        return result

    async def get_evidence(self, evidence_id: str) -> Optional[dict[str, Any]]:
        row = await self.db.fetch_one(
            "SELECT * FROM security_evidence WHERE tenant_id = ? AND evidence_id = ?",
            (self.tenant_id, evidence_id),
        )
        if not row:
            return None
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        except (TypeError, ValueError):
            item["metadata"] = {}
        return item

    async def list_evidence(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT evidence_id FROM security_evidence WHERE tenant_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (self.tenant_id, max(1, min(int(limit), 500))),
        )
        result = []
        for row in rows:
            item = await self.get_evidence(row["evidence_id"])
            if item:
                result.append(item)
        return result

    async def index_evidence(
        self,
        evidence_id: str,
        *,
        title: str,
        document_type: str,
        policy_version: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        evidence = await self.get_evidence(evidence_id)
        if not evidence:
            raise KeyError(evidence_id)
        document_id = f"doc-{uuid.uuid4().hex}"
        await self.db.execute(
            """
            INSERT INTO knowledge_documents (
                document_id, tenant_id, evidence_id, title, document_type,
                policy_version, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                self.tenant_id,
                evidence_id,
                title[:300],
                document_type[:100],
                policy_version,
                json.dumps(_safe(metadata or {}), ensure_ascii=False, sort_keys=True),
            ),
        )
        chunks = chunk_security_document(
            document_id, title[:300], document_type[:100], evidence.get("text_content") or ""
        )
        for ordinal, chunk in enumerate(chunks):
            content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            keywords = sorted(set(chunk.text.casefold().split()))[:100]
            await self.db.execute(
                """
                INSERT INTO knowledge_chunks (
                    chunk_id, document_id, tenant_id, parent_path, ordinal,
                    text_content, keywords_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    document_id,
                    self.tenant_id,
                    chunk.parent_path,
                    ordinal,
                    chunk.text,
                    json.dumps(keywords, ensure_ascii=False),
                    content_hash,
                ),
            )
        return {"document_id": document_id, "evidence_id": evidence_id, "chunk_count": len(chunks)}

    async def load_chunks(
        self,
        *,
        document_types: Optional[Sequence[str]] = None,
        limit: int = 5000,
    ) -> list[SecurityChunk]:
        parameters: list[Any] = [self.tenant_id]
        where = "WHERE c.tenant_id = ?"
        if document_types:
            clean_types = [str(item)[:100] for item in document_types]
            where += " AND d.document_type IN (" + ",".join("?" for _ in clean_types) + ")"
            parameters.extend(clean_types)
        parameters.append(max(1, min(int(limit), 20_000)))
        rows = await self.db.fetch_all(
            "SELECT c.chunk_id, c.document_id, c.text_content, c.parent_path, "
            "d.title, d.document_type, d.metadata_json FROM knowledge_chunks c "
            "JOIN knowledge_documents d ON d.document_id = c.document_id "
            f"{where} ORDER BY c.document_id, c.ordinal LIMIT ?",
            tuple(parameters),
        )
        result = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (TypeError, ValueError):
                metadata = {}
            result.append(
                SecurityChunk(
                    row["chunk_id"], row["document_id"], row["text_content"],
                    row["title"], row["document_type"], row["parent_path"] or "", metadata,
                )
            )
        return result

    async def save_memory(
        self,
        *,
        memory_type: str,
        subject_key: str,
        summary: str,
        evidence_ids: Optional[Iterable[str]] = None,
        confirmed: bool = False,
        confidence: float = 1.0,
        ttl_days: Optional[int] = None,
    ) -> dict[str, Any]:
        if memory_type not in self.MEMORY_TYPES:
            raise ValueError("invalid memory type")
        evidence = list(evidence_ids or [])[:128]
        if memory_type == "incident" and confirmed and not evidence:
            raise ValueError("confirmed incident memory requires evidence")
        if memory_type == "incident" and not confirmed:
            raise ValueError("incident memory must be explicitly confirmed")
        if memory_type == "incident":
            placeholders = ",".join("?" for _ in evidence)
            rows = await self.db.fetch_all(
                "SELECT evidence_id FROM security_evidence "
                f"WHERE tenant_id = ? AND evidence_id IN ({placeholders})",
                (self.tenant_id, *evidence),
            )
            known = {str(row["evidence_id"]) for row in rows}
            unknown = sorted(set(evidence) - known)
            if unknown:
                raise ValueError("incident memory contains unknown evidence IDs")
        expires_at = None
        if ttl_days is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=max(1, min(int(ttl_days), 3650)))
            ).isoformat()
        memory_id = f"mem-{uuid.uuid4().hex}"
        safe_summary = str(_safe(summary))[:8000]
        await self.db.execute(
            """
            INSERT INTO agent_memories (
                memory_id, tenant_id, memory_type, subject_key, summary,
                evidence_ids_json, confidence, confirmed, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id, self.tenant_id, memory_type, subject_key[:256], safe_summary,
                json.dumps(evidence), max(0.0, min(1.0, float(confidence))),
                int(confirmed), expires_at,
            ),
        )
        return (await self.list_memories(memory_id=memory_id))[0]

    async def list_memories(
        self,
        *,
        memory_type: Optional[str] = None,
        subject_key: Optional[str] = None,
        memory_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = ["tenant_id = ?", "(expires_at IS NULL OR julianday(expires_at) > julianday('now'))"]
        parameters: list[Any] = [self.tenant_id]
        for column, value in (
            ("memory_type", memory_type), ("subject_key", subject_key), ("memory_id", memory_id)
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        parameters.append(max(1, min(int(limit), 500)))
        rows = await self.db.fetch_all(
            "SELECT * FROM agent_memories WHERE " + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT ?",
            tuple(parameters),
        )
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["evidence_ids"] = json.loads(item.pop("evidence_ids_json") or "[]")
            except (TypeError, ValueError):
                item["evidence_ids"] = []
            item["confirmed"] = bool(item["confirmed"])
            result.append(item)
        return result

    async def delete_memory(self, memory_id: str) -> bool:
        existing = await self.db.fetch_one(
            "SELECT memory_id FROM agent_memories WHERE tenant_id = ? AND memory_id = ?",
            (self.tenant_id, memory_id),
        )
        if not existing:
            return False
        await self.db.execute(
            "DELETE FROM agent_memories WHERE tenant_id = ? AND memory_id = ?",
            (self.tenant_id, memory_id),
        )
        return True

    async def create_agent_run(self, task_type: str, request: dict[str, Any]) -> dict[str, Any]:
        run_id = f"run-{uuid.uuid4().hex}"
        initial = {"run_id": run_id, "task_type": task_type, "status": "queued"}
        await self.db.execute(
            """
            INSERT INTO security_agent_runs (
                run_id, tenant_id, task_type, status, request_json, state_json
            ) VALUES (?, ?, ?, 'queued', ?, ?)
            """,
            (
                run_id, self.tenant_id, task_type,
                json.dumps(_safe(request), ensure_ascii=False, sort_keys=True),
                json.dumps(initial, ensure_ascii=False, sort_keys=True),
            ),
        )
        result = await self.get_agent_run(run_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("created Agent run could not be loaded")
        return result

    async def update_agent_run(
        self,
        run_id: str,
        *,
        status: str,
        state: dict[str, Any],
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        approval_hash: Optional[str] = None,
    ) -> None:
        completed = datetime.now(timezone.utc).isoformat() if status in {"completed", "failed", "rejected", "cancelled"} else None
        await self.db.execute(
            """
            UPDATE security_agent_runs SET status = ?, state_json = ?, result_json = ?,
                error = ?, approval_hash = COALESCE(?, approval_hash),
                updated_at = CURRENT_TIMESTAMP, completed_at = ?
            WHERE tenant_id = ? AND run_id = ?
            """,
            (
                status,
                json.dumps(_safe(state), ensure_ascii=False, sort_keys=True),
                json.dumps(_safe(result), ensure_ascii=False, sort_keys=True) if result is not None else None,
                str(_safe(error))[:2000] if error else None,
                approval_hash,
                completed,
                self.tenant_id,
                run_id,
            ),
        )

    async def append_agent_event(
        self,
        run_id: str,
        node_name: str,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        row = await self.db.fetch_one(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM security_agent_events WHERE run_id = ?",
            (run_id,),
        )
        seq = int(row["seq"] if row else 0) + 1
        await self.db.execute(
            """
            INSERT INTO security_agent_events (
                event_id, run_id, seq, node_name, event_type, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"ae-{uuid.uuid4().hex}", run_id, seq, node_name[:100], event_type[:50],
                json.dumps(_safe(payload or {}), ensure_ascii=False, sort_keys=True),
            ),
        )

    async def get_agent_run(self, run_id: str) -> Optional[dict[str, Any]]:
        row = await self.db.fetch_one(
            "SELECT * FROM security_agent_runs WHERE tenant_id = ? AND run_id = ?",
            (self.tenant_id, run_id),
        )
        if not row:
            return None
        item = dict(row)
        for source, target, fallback in (
            ("request_json", "request", {}),
            ("state_json", "state", {}),
            ("result_json", "result", None),
        ):
            raw = item.pop(source)
            try:
                item[target] = json.loads(raw) if raw else fallback
            except (TypeError, ValueError):
                item[target] = fallback
        rows = await self.db.fetch_all(
            "SELECT seq, node_name, event_type, payload_json, created_at "
            "FROM security_agent_events WHERE run_id = ? ORDER BY seq",
            (run_id,),
        )
        events = []
        for event_row in rows:
            event = dict(event_row)
            try:
                event["payload"] = json.loads(event.pop("payload_json") or "{}")
            except (TypeError, ValueError):
                event["payload"] = {}
            events.append(event)
        item["events"] = events
        return item

    async def list_agent_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT run_id, task_type, status, created_at, updated_at FROM security_agent_runs "
            "WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
            (self.tenant_id, max(1, min(limit, 100))),
        )
        return [dict(row) for row in rows]


__all__ = ["SecurityOperationsRepository"]
