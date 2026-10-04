"""
Aegis Local Threat Monitor Desktop Application.

This module provides a cross-platform desktop application for monitoring
autonomous AI agents running locally. It includes:
- Local API server for threat analysis
- SQLite database for threat intel persistence
- Desktop UI with dashboard, rules browser, and threat intel views
- System tray integration for background operation

Installation:
    pip install ai-aegis[app]

Usage:
    aegis-app [--port PORT] [--host HOST] [--debug] [--no-tray]
"""

# Single source of truth: the distribution version. Derived from the
# top-level package rather than duplicated, so /health, the startup banner
# and --version cannot drift from the installed package metadata.
from aegis import __version__

__app_name__ = "Aegis Local Threat Monitor"

# Required dependencies for the app
APP_DEPENDENCIES = [
    "webview",  # pywebview
    "fastapi",
    "uvicorn",
    "aiosqlite",
    "sqlalchemy",
    "watchdog",
    "platformdirs",
]


class AppDependencyError(ImportError):
    """Raised when app dependencies are not installed."""

    pass


def check_app_dependencies() -> None:
    """
    Check if all required app dependencies are installed.

    Raises:
        AppDependencyError: If any required dependency is missing.
    """
    missing = []
    for dep in APP_DEPENDENCIES:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)

    if missing:
        raise AppDependencyError(
            f"Missing required dependencies: {', '.join(missing)}\n\n"
            f"The desktop app requires additional dependencies.\n"
            f"Please install with: pip install ai-aegis[app]"
        )


def get_version() -> str:
    """Get the app version string."""
    return __version__


def get_app_name() -> str:
    """Get the application name."""
    return __app_name__
