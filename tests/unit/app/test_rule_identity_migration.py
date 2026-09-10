"""Persistence migration checks for retired community-rule identifiers."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from aegis.app.database.connection import DatabaseConnection
from aegis.app.services.analysis_service import AnalysisService


@pytest.mark.asyncio
async def test_retired_rule_id_is_removed_and_override_is_preserved(tmp_path):
    db = DatabaseConnection(tmp_path / "identity.db")
    await db.connect()
    await db.execute(
        """
        CREATE TABLE community_rules (
            id TEXT PRIMARY KEY, name TEXT, category TEXT, description TEXT,
            severity TEXT, patterns TEXT, enabled INTEGER, source_file TEXT,
            metadata TEXT, loaded_at TEXT
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE rule_overrides (
            id TEXT PRIMARY KEY, original_rule_id TEXT UNIQUE, enabled INTEGER,
            severity TEXT, patterns TEXT, created_at TEXT, updated_at TEXT
        )
        """
    )

    retired_id = "s" + "v_community_example"
    current_id = "aegis_community_example"
    now = datetime.utcnow().isoformat()
    row = ("Example", "prompt_injection", "", "high", json.dumps(["attack"]), 1, "rules.yml", None, now)
    await db.execute(
        "INSERT INTO community_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (retired_id, *row),
    )
    await db.execute(
        "INSERT INTO community_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (current_id, *row),
    )
    await db.execute(
        "INSERT INTO rule_overrides VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("override-1", retired_id, 0, "critical", None, now, now),
    )

    service = AnalysisService(db)
    migrated = await service._migrate_retired_rule_identity()

    assert migrated == 1
    assert await db.fetch_one("SELECT id FROM community_rules WHERE id = ?", (retired_id,)) is None
    override = await db.fetch_one(
        "SELECT original_rule_id, enabled, severity FROM rule_overrides WHERE id = ?",
        ("override-1",),
    )
    assert dict(override) == {
        "original_rule_id": current_id,
        "enabled": 0,
        "severity": "critical",
    }
    await db.disconnect()
