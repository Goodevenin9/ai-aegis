"""
MCP Configuration for Aegis AI Threat Monitor

This module contains configuration classes and utilities for the Aegis
MCP server implementation.

Available Configuration:
- MCPServerConfig: Main MCP server configuration
- SecurityConfig: Security and authentication settings
- PerformanceConfig: Performance and rate limiting settings

Copyright (c) 2025 SecureVector
Copyright (c) 2026 Aegis (derived work; see NOTICE)
Licensed under the Apache License, Version 2.0
"""

try:
    from .server_config import (
        MCPServerConfig,
        SecurityConfig,
        PerformanceConfig,
    )

    MCP_CONFIG_AVAILABLE = True
except ImportError:
    MCP_CONFIG_AVAILABLE = False

    # Dummy classes for when MCP is not available
    class MCPServerConfig:
        def __init__(self):
            raise ImportError("MCP config requires mcp package to be installed")

    class SecurityConfig:
        def __init__(self):
            raise ImportError("MCP config requires mcp package to be installed")

    class PerformanceConfig:
        def __init__(self):
            raise ImportError("MCP config requires mcp package to be installed")

__all__ = [
    "MCPServerConfig",
    "SecurityConfig",
    "PerformanceConfig",
    "MCP_CONFIG_AVAILABLE",
]
