"""
Aegis MCP (Model Context Protocol) Server

This module provides MCP server capabilities for Aegis AI Threat Monitor,
enabling LLMs to securely access threat analysis tools through standardized interfaces.

The MCP server exposes:
- Tools: analyze_prompt, batch_analyze, get_threat_statistics
- Resources: threat detection rules, security policies
- Prompts: analysis workflow templates

Usage:
    from aegis.mcp import AegisMCPServer

    server = AegisMCPServer()
    server.run()

Copyright (c) 2025 SecureVector
Copyright (c) 2026 Aegis (derived work; see NOTICE)
Licensed under the Apache License, Version 2.0
"""

from typing import Optional

try:
    from .server import AegisMCPServer
    from .config.server_config import MCPServerConfig

    # Optional imports - only available if mcp is installed
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

    class AegisMCPServer:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MCP dependencies not installed. Install with: "
                "pip install ai-aegis[mcp]"
            )

    class MCPServerConfig:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MCP dependencies not installed. Install with: "
                "pip install ai-aegis[mcp]"
            )

__version__ = "3.4.0"
__all__ = [
    "AegisMCPServer",
    "MCPServerConfig",
    "MCP_AVAILABLE",
]

def create_mcp_server(
    name: str = "Aegis AI Threat Monitor",
    api_key: Optional[str] = None,
    **kwargs
) -> "AegisMCPServer":
    """
    Create a Aegis MCP server instance.

    Args:
        name: Server name for MCP identification
        api_key: Optional API key for authentication
        **kwargs: Additional configuration options

    Returns:
        AegisMCPServer instance

    Raises:
        ImportError: If MCP dependencies not installed
    """
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP dependencies not installed. Install with: "
            "pip install ai-aegis[mcp]"
        )

    return AegisMCPServer(name=name, api_key=api_key, **kwargs)

def check_mcp_dependencies() -> bool:
    """
    Check if MCP dependencies are available.

    Returns:
        True if MCP can be used, False otherwise
    """
    return MCP_AVAILABLE
