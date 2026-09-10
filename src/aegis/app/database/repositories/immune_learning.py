"""Persistence and lifecycle governance for session-immunity antibodies."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from aegis.app.database.connection import DatabaseConnection
from aegis.app.services.immune_learning import (
    AntibodyPattern,
    BehaviorProfile,
    ImmuneMatchResult,
    ImmuneMatcher,
    transition_antibody,
)


class ImmuneLearningRepository:
    def __init__(self, db: DatabaseConnection, tenant_id: str = "local") -> None:
        self.db = db
        self.tenant_id = tenant_id.strip() or "local"

    @staticmethod
    def _pattern_json(profile: BehaviorProfile) -> str:
        return json.dumps(
            {
                "tool_sequence": list(profile.tool_sequence[-32:]),
                "capability_sequence": list(profile.capability_sequence[-32:]),
                "radius_sequence": list(profile.radius_sequence[-32:]),
                "required_features": sorted(profile.features),
                "optional_features": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    async def create_candidate(
        self,
        *,
        name: str,
        profile: BehaviorProfile,
        description: str = "",
        source_session_key: Optional[str] = None,
        source_evidence_ids: list[str] | None = None,
        similarity_threshold: float = 0.75,
        max_score_delta: int = 20,
        antibody_id: Optional[str] = None,
    ) -> dict[str, Any]:
        pattern = AntibodyPattern(
            antibody_id=antibody_id or f"ab-{uuid.uuid4().hex}",
            name=name,
            status="candidate",
            tool_sequence=profile.tool_sequence[-32:],
            capability_sequence=profile.capability_sequence[-32:],
            radius_sequence=profile.radius_sequence[-32:],
            required_features=profile.features,
            similarity_threshold=similarity_threshold,
            max_score_delta=max_score_delta,
        )
        await self.db.execute(
            """
            INSERT INTO immune_antibodies (
                antibody_id, tenant_id, name, description, status, pattern_json,
                similarity_threshold, max_score_delta, source_session_key,
                source_evidence_json
            ) VALUES (?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?)
            """,
            (
                pattern.antibody_id,
                self.tenant_id,
                pattern.name,
                description[:2000],
                self._pattern_json(profile),
                pattern.similarity_threshold,
                pattern.max_score_delta,
                source_session_key,
                json.dumps(list(source_evidence_ids or [])[:128]),
            ),
        )
        result = await self.get(pattern.antibody_id)
        if result is None:  # pragma: no cover - INSERT then SELECT invariant
            raise RuntimeError("created antibody could not be loaded")
        return result

    async def get(self, antibody_id: str) -> Optional[dict[str, Any]]:
        row = await self.db.fetch_one(
            "SELECT * FROM immune_antibodies WHERE tenant_id = ? AND antibody_id = ?",
            (self.tenant_id, antibody_id),
        )
        return self._decode_row(dict(row)) if row else None

    async def list(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        if status:
            rows = await self.db.fetch_all(
                "SELECT * FROM immune_antibodies "
                "WHERE tenant_id = ? AND status = ? ORDER BY updated_at DESC",
                (self.tenant_id, status),
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM immune_antibodies "
                "WHERE tenant_id = ? ORDER BY updated_at DESC",
                (self.tenant_id,),
            )
        return [self._decode_row(dict(row)) for row in rows]

    async def transition(
        self,
        antibody_id: str,
        target: str,
        *,
        approved_by: Optional[str] = None,
    ) -> dict[str, Any]:
        current = await self.get(antibody_id)
        if current is None:
            raise KeyError(antibody_id)
        new_status = transition_antibody(
            current["status"], target, approved=bool(approved_by)
        )
        approved_at = datetime.now(timezone.utc).isoformat() if approved_by else None
        await self.db.execute(
            """
            UPDATE immune_antibodies SET status = ?, approved_by = ?, approved_at = ?,
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND antibody_id = ?
            """,
            (new_status, approved_by, approved_at, self.tenant_id, antibody_id),
        )
        result = await self.get(antibody_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("updated antibody could not be loaded")
        return result

    async def load_matcher(self, max_total_score_delta: int = 25) -> ImmuneMatcher:
        rows = await self.list()
        patterns = [self._to_pattern(row) for row in rows if row["status"] != "retired"]
        return ImmuneMatcher(patterns, max_total_score_delta=max_total_score_delta)

    async def record_matches(
        self,
        session_key: str,
        result: ImmuneMatchResult,
    ) -> None:
        for match in result.matches:
            match_id = f"im-{uuid.uuid4().hex}"
            await self.db.execute(
                """
                INSERT INTO immune_matches (
                    match_id, antibody_id, tenant_id, session_key, similarity,
                    score_delta, effective, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    match.antibody_id,
                    self.tenant_id,
                    session_key,
                    match.similarity,
                    match.score_delta,
                    int(match.effective),
                    json.dumps({"matched_features": match.matched_features}),
                ),
            )
            await self.db.execute(
                """
                UPDATE immune_antibodies SET match_count = match_count + 1,
                    last_matched_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND antibody_id = ?
                """,
                (self.tenant_id, match.antibody_id),
            )

    async def list_matches(
        self, *, session_key: Optional[str] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        if session_key:
            rows = await self.db.fetch_all(
                "SELECT * FROM immune_matches WHERE tenant_id = ? AND session_key = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (self.tenant_id, session_key, bounded),
            )
        else:
            rows = await self.db.fetch_all(
                "SELECT * FROM immune_matches WHERE tenant_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (self.tenant_id, bounded),
            )
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except (TypeError, ValueError):
                item["details"] = {}
            item["effective"] = bool(item["effective"])
            result.append(item)
        return result

    @staticmethod
    def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
        for key in ("pattern_json", "source_evidence_json"):
            try:
                row[key.removesuffix("_json")] = json.loads(row.pop(key) or "{}")
            except (TypeError, ValueError):
                row[key.removesuffix("_json")] = {} if key == "pattern_json" else []
        return row

    @staticmethod
    def _to_pattern(row: dict[str, Any]) -> AntibodyPattern:
        pattern = row.get("pattern") or {}
        return AntibodyPattern(
            antibody_id=row["antibody_id"],
            name=row["name"],
            status=row["status"],
            tool_sequence=tuple(pattern.get("tool_sequence") or ()),
            capability_sequence=tuple(pattern.get("capability_sequence") or ()),
            radius_sequence=tuple(pattern.get("radius_sequence") or ()),
            required_features=frozenset(pattern.get("required_features") or ()),
            optional_features=frozenset(pattern.get("optional_features") or ()),
            similarity_threshold=float(row["similarity_threshold"]),
            max_score_delta=int(row["max_score_delta"]),
            weight=(float(row["weight"]) * 0.5 if row["status"] == "decaying" else float(row["weight"])),
        )


__all__ = ["ImmuneLearningRepository"]
