"""Route-level tests for tool_permissions routes — runtime_kind plumbing.

Covers the slice of Task 3:
- AuditLogRequest accepts an optional runtime_kind field
- Defaults to None when omitted
- get_audit_log surfaces runtime_kind in returned entries
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.custom_tools import CustomToolsRepository
from aegis.app.server.routes.tool_permissions import AuditLogRequest


# --- Pydantic model -------------------------------------------------------


def test_audit_log_request_accepts_runtime_kind():
    req = AuditLogRequest(
        tool_id="server-x:tool_a",
        function_name="tool_a",
        action="allow",
        runtime_kind="claude-code",
    )
    assert req.runtime_kind == "claude-code"


def test_audit_log_request_defaults_runtime_kind_to_none():
    req = AuditLogRequest(
        tool_id="server-x:tool_a",
        function_name="tool_a",
        action="allow",
    )
    assert req.runtime_kind is None


# --- GET surface ---------------------------------------------------------


async def _build_repo(tmp_path) -> CustomToolsRepository:
    db = DatabaseConnection(tmp_path / "test.db")
    await run_migrations(db)
    return CustomToolsRepository(db)


@pytest.mark.asyncio
async def test_get_audit_log_surfaces_runtime_kind(tmp_path):
    """Rows written with runtime_kind must appear with that field in get_audit_log."""
    repo = await _build_repo(tmp_path)

    await repo.log_tool_call_audit(
        tool_id="srv:one",
        function_name="one",
        action="allow",
        runtime_kind="claude-code",
    )
    await repo.log_tool_call_audit(
        tool_id="srv:two",
        function_name="two",
        action="block",
        # runtime_kind omitted → NULL
    )

    entries, total = await repo.get_audit_log(limit=10)
    assert total == 2
    # Newest first
    by_tool = {e["tool_id"]: e for e in entries}
    assert "runtime_kind" in by_tool["srv:one"]
    assert by_tool["srv:one"]["runtime_kind"] == "claude-code"
    assert by_tool["srv:two"]["runtime_kind"] is None

    await repo.db.disconnect()


@pytest.mark.asyncio
async def test_get_audit_log_filters_keep_runtime_kind(tmp_path):
    """action_filter path must also include runtime_kind in the SELECT."""
    repo = await _build_repo(tmp_path)

    await repo.log_tool_call_audit(
        tool_id="srv:blocked", function_name="blocked",
        action="block", runtime_kind="openclaw",
    )
    await repo.log_tool_call_audit(
        tool_id="srv:allowed", function_name="allowed",
        action="allow", runtime_kind="claude-code",
    )

    entries, total = await repo.get_audit_log(limit=10, action_filter="block")
    assert total == 1
    assert entries[0]["runtime_kind"] == "openclaw"

    await repo.db.disconnect()


# --- Custom-tool metadata edit --------------------------------------------
#
# The UI's "Save Changes" button called API.updateCustomTool(), which existed
# on neither the client nor the server: the only PUT on that path sets
# default_permission. Editing a tool's name always failed. These cover the
# repository half plus the request model's guarantees.


async def _tools_repo(tmp_path) -> CustomToolsRepository:
    db = DatabaseConnection(tmp_path / "tools.db")
    await run_migrations(db)
    return CustomToolsRepository(db)


@pytest.mark.asyncio
async def test_update_metadata_changes_only_supplied_fields(tmp_path):
    repo = await _tools_repo(tmp_path)
    await repo.create_custom_tool(
        tool_id="srv:t1", name="Original", risk="read",
        default_permission="block", description="before",
    )

    tool = await repo.update_custom_tool_metadata("srv:t1", name="Renamed", risk="admin")

    assert tool["name"] == "Renamed"
    assert tool["risk"] == "admin"
    # Untouched fields survive a partial edit.
    assert tool["description"] == "before"
    assert tool["default_permission"] == "block"


@pytest.mark.asyncio
async def test_update_metadata_never_touches_permission(tmp_path):
    """Renaming a tool must not be able to change what it may do."""
    repo = await _tools_repo(tmp_path)
    await repo.create_custom_tool(
        tool_id="srv:t2", name="T2", risk="read",
        default_permission="block", description="",
    )

    await repo.update_custom_tool_metadata(
        "srv:t2", name="Harmless Rename", description="x", risk="admin"
    )

    tool = await repo.get_custom_tool("srv:t2")
    assert tool["default_permission"] == "block"


@pytest.mark.asyncio
async def test_update_metadata_with_no_fields_is_a_noop(tmp_path):
    repo = await _tools_repo(tmp_path)
    await repo.create_custom_tool(
        tool_id="srv:t3", name="T3", risk="write",
        default_permission="allow", description="d",
    )

    tool = await repo.update_custom_tool_metadata("srv:t3")

    assert tool["name"] == "T3"
    assert tool["risk"] == "write"
    assert tool["description"] == "d"


@pytest.mark.asyncio
async def test_update_metadata_on_missing_tool_returns_none(tmp_path):
    repo = await _tools_repo(tmp_path)
    assert await repo.update_custom_tool_metadata("nope", name="x") is None


def test_update_request_rejects_bad_risk_and_empty_name():
    from pydantic import ValidationError
    from aegis.app.server.routes.tool_permissions import UpdateCustomToolRequest

    with pytest.raises(ValidationError):
        UpdateCustomToolRequest(risk="superuser")
    with pytest.raises(ValidationError):
        UpdateCustomToolRequest(name="")

    # All fields optional: a rename-only edit is valid.
    req = UpdateCustomToolRequest(name="Just A Rename")
    assert req.description is None and req.risk is None


def test_update_request_has_no_permission_field():
    """Structural guard: if someone adds default_permission here, a label edit
    silently becomes an enforcement change."""
    from aegis.app.server.routes.tool_permissions import UpdateCustomToolRequest

    assert "default_permission" not in UpdateCustomToolRequest.model_fields


# --- Call rate-limit endpoints --------------------------------------------
#
# api.js has always called `PUT .../{tool_id}/rate-limit` for both essential
# and custom tools, but neither route existed: the DB columns (migration v11)
# and the repository methods were built and then orphaned, so every such call
# 404'd. These cover the routes that now wire them up.


@pytest.mark.asyncio
async def test_essential_rate_limit_route_creates_then_clears(tmp_path, monkeypatch):
    from aegis.app.server.routes import tool_permissions
    from aegis.app.server.routes.tool_permissions import RateLimitRequest

    db = DatabaseConnection(tmp_path / "essential-rate-limit.db")
    await run_migrations(db)
    monkeypatch.setattr(tool_permissions, "get_database", lambda: db)

    created = await tool_permissions.upsert_override_rate_limit(
        "Bash", RateLimitRequest(max_calls=5, window_seconds=60)
    )
    assert created["rate_limit_max_calls"] == 5
    assert created["rate_limit_window_seconds"] == 60
    # A limit must not change what the tool is allowed to do.
    assert created["action"] == "allow"

    cleared = await tool_permissions.upsert_override_rate_limit(
        "Bash", RateLimitRequest()
    )
    assert cleared["rate_limit_max_calls"] is None
    assert cleared["rate_limit_window_seconds"] is None

    await db.disconnect()


@pytest.mark.asyncio
async def test_essential_rate_limit_rejects_half_specified_limit(monkeypatch):
    from aegis.app.server.routes import tool_permissions
    from aegis.app.server.routes.tool_permissions import RateLimitRequest

    with pytest.raises(HTTPException) as exc:
        await tool_permissions.upsert_override_rate_limit(
            "Bash", RateLimitRequest(max_calls=5)
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_essential_rate_limit_rejects_unknown_tool(monkeypatch):
    from aegis.app.server.routes import tool_permissions
    from aegis.app.server.routes.tool_permissions import RateLimitRequest

    with pytest.raises(HTTPException) as exc:
        await tool_permissions.upsert_override_rate_limit(
            "not-a-real-tool", RateLimitRequest(max_calls=5, window_seconds=60)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_custom_rate_limit_route_updates_and_404s(tmp_path, monkeypatch):
    from aegis.app.server.routes import tool_permissions
    from aegis.app.server.routes.tool_permissions import RateLimitRequest

    db = DatabaseConnection(tmp_path / "custom-rate-limit.db")
    await run_migrations(db)
    repo = CustomToolsRepository(db)
    await repo.create_custom_tool(
        tool_id="srv:limited", name="Limited", risk="write",
        default_permission="allow", description="",
    )
    monkeypatch.setattr(tool_permissions, "get_database", lambda: db)

    tool = await tool_permissions.update_custom_tool_rate_limit(
        "srv:limited", RateLimitRequest(max_calls=3, window_seconds=30)
    )
    assert tool["rate_limit_max_calls"] == 3
    assert tool["rate_limit_window_seconds"] == 30
    # Permission is untouched by a rate-limit edit.
    assert tool["default_permission"] == "allow"

    with pytest.raises(HTTPException) as exc:
        await tool_permissions.update_custom_tool_rate_limit(
            "srv:missing", RateLimitRequest(max_calls=1, window_seconds=1)
        )
    assert exc.value.status_code == 404

    await db.disconnect()


def test_rate_limit_request_rejects_zero_window_and_bad_type():
    from pydantic import ValidationError
    from aegis.app.server.routes.tool_permissions import RateLimitRequest

    with pytest.raises(ValidationError):
        RateLimitRequest(max_calls=0, window_seconds=60)
    with pytest.raises(ValidationError):
        RateLimitRequest(max_calls=5, window_seconds=0)
    # Both-null (clear) is the only single-field-free valid shape.
    assert RateLimitRequest().max_calls is None
