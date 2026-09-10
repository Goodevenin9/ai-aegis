"""Persistence adapter for P1 five-stage configuration and manifests."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Optional

from aegis.app.database.connection import DatabaseConnection
from aegis.app.services.pretool_pipeline import KNOWN_CAPABILITIES, PipelineConfig


class RuntimePolicyRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def get_config(self) -> PipelineConfig:
        row = await self.db.fetch_one(
            "SELECT config_json FROM runtime_pipeline_config WHERE id = 1"
        )
        if not row:
            return PipelineConfig()
        try:
            value = json.loads(row["config_json"])
            allowed = {field for field in asdict(PipelineConfig())}
            return PipelineConfig(**{key: value[key] for key in allowed if key in value})
        except (TypeError, ValueError):
            return PipelineConfig()

    async def save_config(self, config: PipelineConfig) -> dict[str, Any]:
        payload = json.dumps(asdict(config), sort_keys=True)
        await self.db.execute(
            """
            INSERT INTO runtime_pipeline_config (id, config_json) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET
                config_json = excluded.config_json,
                version = runtime_pipeline_config.version + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (payload,),
        )
        row = await self.db.fetch_one(
            "SELECT version, updated_at FROM runtime_pipeline_config WHERE id = 1"
        )
        return {"config": asdict(config), "version": row["version"], "updated_at": row["updated_at"]}

    async def get_manifest(
        self, runtime_kind: str, manifest_id: str, session_id: str = "*"
    ) -> Optional[dict[str, Any]]:
        row = await self.db.fetch_one(
            """SELECT runtime_kind, manifest_id, session_id, capabilities_json, project_root,
                      description, version, updated_at
               FROM runtime_capability_manifests
               WHERE runtime_kind = ? AND manifest_id = ? AND session_id = ?""",
            (runtime_kind, manifest_id, session_id),
        )
        if not row:
            return None
        result = dict(row)
        try:
            result["allowed_capabilities"] = json.loads(result.pop("capabilities_json"))
        except (TypeError, ValueError):
            result["allowed_capabilities"] = []
        return result

    async def save_manifest(
        self,
        runtime_kind: str,
        manifest_id: str,
        allowed_capabilities: list[str],
        project_root: Optional[str],
        description: str,
        session_id: str = "*",
    ) -> dict[str, Any]:
        capabilities = sorted(set(allowed_capabilities))
        unknown = set(capabilities) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capabilities: {', '.join(sorted(unknown))}")
        await self.db.execute(
            """
            INSERT INTO runtime_capability_manifests
                (runtime_kind, manifest_id, session_id, capabilities_json, project_root, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(runtime_kind, manifest_id, session_id) DO UPDATE SET
                capabilities_json = excluded.capabilities_json,
                project_root = excluded.project_root,
                description = excluded.description,
                version = runtime_capability_manifests.version + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                runtime_kind, manifest_id, session_id, json.dumps(capabilities),
                project_root, description,
            ),
        )
        return await self.get_manifest(runtime_kind, manifest_id, session_id)  # type: ignore[return-value]

    async def list_manifests(self) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT runtime_kind, manifest_id, session_id FROM runtime_capability_manifests ORDER BY updated_at DESC"
        )
        result = []
        for row in rows:
            item = await self.get_manifest(
                row["runtime_kind"], row["manifest_id"], row["session_id"]
            )
            if item:
                result.append(item)
        return result

    async def delete_manifest(
        self, runtime_kind: str, manifest_id: str, session_id: str = "*"
    ) -> bool:
        existing = await self.get_manifest(runtime_kind, manifest_id, session_id)
        if not existing:
            return False
        await self.db.execute(
            "DELETE FROM runtime_capability_manifests WHERE runtime_kind = ? AND manifest_id = ? AND session_id = ?",
            (runtime_kind, manifest_id, session_id),
        )
        return True


__all__ = ["RuntimePolicyRepository"]
