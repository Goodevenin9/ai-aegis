"""Aegis Guard for Hermes (NousResearch ``hermes-agent``).

Zero code: this package registers a Hermes plugin through the
``hermes_agent.plugins`` entry point, so the plugin manager auto-attaches it
on startup in every mode (the interactive ``hermes`` CLI, ``hermes gateway``
for Telegram/Discord/Slack, and the ACP/Zed adapter). A denied tool is stopped
through Hermes's own ``pre_tool_call`` block directive with an
``Aegis Guard:`` reason.

    pip install aegis-sdk-hermes
    hermes                          # observe (log-only, default)
    AEGIS_SDK_MODE=enforce hermes   # block denied tools

Driving ``AIAgent`` as a library without the plugin manager?

    from aegis_sdk_hermes import install
    install(mode="enforce")

Decisions are tagged ``runtime_kind="hermes"`` on the shared audit chain.
"""
from __future__ import annotations

from ._core import (  # noqa: F401
    MODE_ENFORCE,
    MODE_OBSERVE,
    AegisClient,
    Verdict,
    resolve_mode,
)
from .plugin import AegisGuard, install
from .tool_id import resolve_candidates  # noqa: F401

__all__ = [
    "install",
    "AegisGuard",
    "AegisClient",
    "Verdict",
    "resolve_candidates",
    "MODE_ENFORCE",
    "MODE_OBSERVE",
]
