"""Closed registry of read-only tools available to the security investigator."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable
from pydantic import BaseModel, ConfigDict, Field


class EvidenceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(min_length=1, max_length=128)


class SessionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_key: str = Field(min_length=1, max_length=256)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SecurityToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[type[BaseModel], Callable[..., Awaitable[Any]], float]] = {}

    def register(self, name: str, schema: type[BaseModel], handler: Callable[..., Awaitable[Any]], timeout: float = 10):
        if name in self._tools:
            raise ValueError("Duplicate security tool")
        self._tools[name] = (schema, handler, timeout)

    def catalog(self) -> list[dict[str, Any]]:
        return [{"name": name, "parameters": schema.model_json_schema(), "read_only": True,
                 "timeout_seconds": timeout, "required_role": "local_operator"}
                for name, (schema, _, timeout) in self._tools.items()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ValueError("Unknown or unauthorized security tool")
        schema, handler, timeout = self._tools[name]
        validated = schema.model_validate(arguments)
        return await asyncio.wait_for(handler(**validated.model_dump()), timeout=timeout)
