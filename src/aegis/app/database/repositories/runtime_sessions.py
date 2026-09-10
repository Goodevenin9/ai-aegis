"""Persistence adapter for session drift state and causal intent/behaviour events."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from aegis.app.database.connection import DatabaseConnection
from aegis.app.utils.redaction import redact_secrets

MAX_CONTENT_CHARS = 8_000
MAX_PAYLOAD_CHARS = 24_000
GENESIS_HASH = "0" * 64


def _redact_text(value: str) -> str:
    redacted, _ = redact_secrets(str(value), direction="outgoing")
    return str(redacted)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {str(k): _redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value))


def _canonical_event(
    session_key: str,
    seq: int,
    event_type: str,
    turn_index: Optional[int],
    content: Optional[str],
    payload_json: str,
    created_at: str,
    prev_hash: str,
) -> bytes:
    value = {
        "session_key": session_key,
        "seq": seq,
        "event_type": event_type,
        "turn_index": turn_index,
        "content": content,
        "payload": payload_json,
        "created_at": created_at,
        "prev_hash": prev_hash,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class RuntimeSessionRepository:
    """Deep module for durable state, event append, timeline reads and integrity."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def save_state(
        self,
        *,
        session_key: str,
        runtime_kind: str,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        safe_state = _redact_value(state)
        state_json = json.dumps(safe_state, ensure_ascii=False, sort_keys=True)
        drift_score = max(0, min(100, int(safe_state.get("drift_score", 0) or 0)))
        risk_level = (
            "blocked" if drift_score >= 80 else
            "elevated" if drift_score >= 40 else
            "guarded" if drift_score > 0 else "clear"
        )
        preview = _redact_text(str(safe_state.get("original_intent") or ""))[:240] or None
        await self.db.execute(
            """
            INSERT INTO runtime_session_states (
                session_key, runtime_kind, session_id, state_json, drift_score,
                risk_level, original_intent_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_key) DO UPDATE SET
                runtime_kind = excluded.runtime_kind,
                session_id = excluded.session_id,
                state_json = excluded.state_json,
                drift_score = excluded.drift_score,
                risk_level = excluded.risk_level,
                original_intent_preview = excluded.original_intent_preview,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_key, runtime_kind, session_id, state_json, drift_score, risk_level, preview),
        )

    async def load_state(self, session_key: str) -> Optional[dict[str, Any]]:
        row = await self.db.fetch_one(
            "SELECT state_json FROM runtime_session_states WHERE session_key = ?",
            (session_key,),
        )
        if not row:
            return None
        try:
            value = json.loads(row["state_json"])
            return value if isinstance(value, dict) else None
        except (TypeError, ValueError):
            return None

    async def delete_state(self, session_key: str) -> None:
        await self.db.execute(
            "DELETE FROM runtime_session_states WHERE session_key = ?", (session_key,)
        )

    async def delete_session(self, session_key: str) -> None:
        """Delete state and its recovery source for an explicit session reset."""

        await self.db.execute(
            "DELETE FROM runtime_session_events WHERE session_key = ?", (session_key,)
        )
        await self.delete_state(session_key)

    async def append_event(
        self,
        *,
        session_key: str,
        runtime_kind: str,
        session_id: str,
        event_type: str,
        turn_index: Optional[int] = None,
        content: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        safe_content = _redact_text(content)[:MAX_CONTENT_CHARS] if content else None
        safe_payload = _redact_value(payload or {})
        payload_json = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True)
        if len(payload_json) > MAX_PAYLOAD_CHARS:
            payload_json = json.dumps(
                {"truncated": True, "preview": payload_json[:MAX_PAYLOAD_CHARS]},
                ensure_ascii=False,
                sort_keys=True,
            )
        created_at = datetime.now(timezone.utc).isoformat()
        for _attempt in range(3):
            last = await self.db.fetch_one(
                "SELECT seq, row_hash FROM runtime_session_events "
                "WHERE session_key = ? ORDER BY seq DESC LIMIT 1",
                (session_key,),
            )
            seq = int(last["seq"]) + 1 if last else 1
            prev_hash = str(last["row_hash"]) if last else GENESIS_HASH
            row_hash = hashlib.sha256(
                _canonical_event(
                    session_key, seq, event_type, turn_index, safe_content,
                    payload_json, created_at, prev_hash,
                )
            ).hexdigest()
            try:
                await self.db.execute(
                    """
                    INSERT INTO runtime_session_events (
                        session_key, runtime_kind, session_id, seq, event_type,
                        turn_index, content, payload, created_at, prev_hash, row_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_key, runtime_kind, session_id, seq, event_type,
                        turn_index, safe_content, payload_json, created_at,
                        prev_hash, row_hash,
                    ),
                )
                return {"seq": seq, "prev_hash": prev_hash, "row_hash": row_hash}
            except aiosqlite.IntegrityError:
                continue
        raise RuntimeError("could not allocate a runtime event sequence")

    async def get_timeline(self, session_key: str, limit: int = 500) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            """
            SELECT seq, runtime_kind, session_id, event_type, turn_index,
                   content, payload, created_at, prev_hash, row_hash
            FROM runtime_session_events
            WHERE session_key = ? ORDER BY seq ASC LIMIT ?
            """,
            (session_key, max(1, min(int(limit), 2000))),
        )
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"] or "{}")
            except (TypeError, ValueError):
                item["payload"] = {}
            result.append(item)
        return result

    async def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self.db.fetch_all(
            """
            SELECT s.session_key, s.runtime_kind, s.session_id, s.drift_score,
                   s.risk_level, s.original_intent_preview, s.created_at, s.updated_at,
                   (SELECT e.event_type FROM runtime_session_events e
                    WHERE e.session_key = s.session_key ORDER BY e.seq DESC LIMIT 1) AS last_event,
                   (SELECT json_extract(e.payload, '$.action') FROM runtime_session_events e
                    WHERE e.session_key = s.session_key AND json_extract(e.payload, '$.action') IS NOT NULL
                    ORDER BY e.seq DESC LIMIT 1) AS last_action,
                   (SELECT COUNT(*) FROM runtime_session_events e
                    WHERE e.session_key = s.session_key) AS event_count
            FROM runtime_session_states s
            ORDER BY s.updated_at DESC LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        )
        return [dict(row) for row in rows]

    async def verify_event_chain(self, session_key: str) -> dict[str, Any]:
        rows = await self.db.fetch_all(
            """
            SELECT seq, runtime_kind, session_id, event_type, turn_index,
                   content, payload, created_at, prev_hash, row_hash
            FROM runtime_session_events
            WHERE session_key = ? ORDER BY seq ASC
            """,
            (session_key,),
        )
        timeline = []
        for row in rows:
            event = dict(row)
            try:
                event["payload"] = json.loads(event["payload"] or "{}")
            except (TypeError, ValueError):
                event["payload"] = {}
            timeline.append(event)
        expected_prev = GENESIS_HASH
        expected_seq = 1
        for row in timeline:
            payload_json = json.dumps(row["payload"], ensure_ascii=False, sort_keys=True)
            calculated = hashlib.sha256(
                _canonical_event(
                    session_key, expected_seq, row["event_type"], row["turn_index"],
                    row["content"], payload_json, row["created_at"], expected_prev,
                )
            ).hexdigest()
            if (
                row["seq"] != expected_seq
                or row["prev_hash"] != expected_prev
                or row["row_hash"] != calculated
            ):
                return {"valid": False, "broken_seq": row["seq"], "checked": expected_seq - 1}
            expected_prev = row["row_hash"]
            expected_seq += 1
        return {"valid": True, "broken_seq": None, "checked": len(timeline)}

    async def recover_state_from_events(self, session_key: str) -> Optional[dict[str, Any]]:
        """Recover the newest state snapshot only from an intact audit chain."""

        integrity = await self.verify_event_chain(session_key)
        if not integrity["valid"]:
            return None
        rows = await self.db.fetch_all(
            "SELECT payload FROM runtime_session_events WHERE session_key = ? ORDER BY seq DESC",
            (session_key,),
        )
        timeline = []
        for row in rows:
            try:
                timeline.append({"payload": json.loads(row["payload"] or "{}")})
            except (TypeError, ValueError):
                timeline.append({"payload": {}})
        for event in timeline:
            snapshot = event.get("payload", {}).get("state_snapshot")
            if isinstance(snapshot, dict):
                return snapshot
        return None


__all__ = ["RuntimeSessionRepository"]
