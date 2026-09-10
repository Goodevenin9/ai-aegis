"""Small SQLite persistence layer for the self-hosted control plane."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ControlPlaneStore:
    """Transactional repository with no external database dependency."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS enrollment_tokens (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT UNIQUE NOT NULL,
                    user_email TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    device_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    bearer_hash TEXT UNIQUE NOT NULL,
                    signing_key TEXT NOT NULL,
                    enrolled_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    last_applied_version INTEGER
                );
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    key_hash TEXT UNIQUE NOT NULL,
                    user_email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    rules_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policy_applied_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    bundle_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    applied_at TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                """
            )

    def create_api_key(
        self, *, key_id: str, api_key: str, user_email: str, name: str
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO api_keys (id, key_hash, user_email, name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key_id, token_digest(api_key), user_email, name, utc_now()),
            )

    def authenticate_api_key(self, api_key: str) -> Optional[dict[str, Any]]:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, user_email, name, created_at FROM api_keys WHERE key_hash = ?",
                (token_digest(api_key),),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
            return dict(row)

    def create_enrollment_token(
        self, *, token_id: str, token: str, user_email: str, expires_at: str
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO enrollment_tokens "
                "(id, token_hash, user_email, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token_id, token_digest(token), user_email, expires_at, utc_now()),
            )

    def consume_enrollment_token(self, token: str) -> tuple[str, Optional[dict[str, Any]]]:
        """Atomically consume a token and return ``(status, row)``."""
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM enrollment_tokens WHERE token_hash = ?",
                (token_digest(token),),
            ).fetchone()
            if row is None:
                return "invalid", None
            data = dict(row)
            if data["used_at"]:
                return "used", data
            if datetime.fromisoformat(data["expires_at"]) <= datetime.now(timezone.utc):
                return "expired", data
            db.execute(
                "UPDATE enrollment_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
                (now, data["id"]),
            )
            return "ok", data

    def create_device(
        self,
        *,
        record_id: str,
        device_id: str,
        user_id: str,
        user_email: str,
        bearer_token: str,
        signing_key: str,
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO devices "
                "(id, device_id, user_id, user_email, bearer_hash, signing_key, enrolled_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    device_id,
                    user_id,
                    user_email,
                    token_digest(bearer_token),
                    signing_key,
                    utc_now(),
                ),
            )

    def device_by_id(self, device_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            return dict(row) if row else None

    def authenticate_device(self, device_id: str, token: str) -> Optional[dict[str, Any]]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM devices WHERE device_id = ? AND bearer_hash = ?",
                (device_id, token_digest(token)),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE devices SET last_seen_at = ? WHERE device_id = ?",
                (utc_now(), device_id),
            )
            return dict(row)

    def upsert_policy(
        self, *, policy_id: str, name: str, mode: str, rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        with self._connect() as db:
            current = db.execute(
                "SELECT version FROM policies WHERE policy_id = ?", (policy_id,)
            ).fetchone()
            version = int(current["version"]) + 1 if current else 1
            updated_at = utc_now()
            db.execute(
                "INSERT INTO policies (policy_id, name, version, mode, rules_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(policy_id) DO UPDATE SET name=excluded.name, "
                "version=excluded.version, mode=excluded.mode, rules_json=excluded.rules_json, "
                "updated_at=excluded.updated_at",
                (policy_id, name, version, mode, json.dumps(rules), updated_at),
            )
        return {
            "policy_id": policy_id,
            "name": name,
            "version": version,
            "mode": mode,
            "rules": rules,
            "updated_at": updated_at,
        }

    def latest_policy(self) -> Optional[dict[str, Any]]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM policies ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["rules"] = json.loads(data.pop("rules_json"))
        return data

    def record_applied(self, event: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO policy_applied_events "
                "(device_id, bundle_id, policy_id, version, status, error, applied_at, received_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event["device_id"],
                    event["bundle_id"],
                    event["policy_id"],
                    event["version"],
                    event["status"],
                    event.get("error"),
                    event["applied_at"],
                    utc_now(),
                ),
            )
            if event["status"] == "ok":
                db.execute(
                    "UPDATE devices SET last_applied_version = ?, last_seen_at = ? "
                    "WHERE device_id = ?",
                    (event["version"], utc_now(), event["device_id"]),
                )

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, device_id, user_id, user_email, enrolled_at, last_seen_at, "
                "last_applied_version FROM devices ORDER BY enrolled_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
