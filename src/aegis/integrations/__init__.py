"""Aegis integrations for various AI agent platforms."""

try:
    from .openclaw_proxy import AegisProxy
except ImportError:
    AegisProxy = None  # type: ignore[assignment,misc]

__all__ = ["AegisProxy"]
