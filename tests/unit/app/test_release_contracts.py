"""Release contracts that must hold for a shippable build.

These guard the two failure modes the 2026-09-10 audit found:

- the product version was reported differently by /health, the CLI, the MCP
  server and the package metadata (drift after a release bump);
- an unknown ``/api/*`` path returned HTTP 200 + the SPA HTML shell, which
  breaks every JSON API consumer and surfaced as a ``JSONDecodeError`` in the
  live integration tests.
"""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

import aegis
import aegis.app
from aegis.app.server.app import create_app
from aegis.mcp.config.server_config import MCPServerConfig

ROOT = Path(__file__).parents[3]
SRC = ROOT / "src" / "aegis"


def test_all_product_versions_report_the_same_value():
    """One version across the package, the web app, and the MCP server."""
    assert aegis.app.__version__ == aegis.__version__

    # FastAPI's info.version is what /health and the docs report.
    schema = create_app().openapi()
    assert schema["info"]["version"] == aegis.__version__

    assert MCPServerConfig().version == aegis.__version__


def test_version_is_defined_before_any_import_in_the_package_init():
    """A late ``__version__`` made ``aegis.mcp.config`` raise ImportError while
    the package was still initialising, which silently flipped the MCP
    detection to False and failed the release workflow's pre-build check.
    The version must be assigned before the first relative import."""
    source = (SRC / "__init__.py").read_text(encoding="utf-8")
    version_at = source.index('__version__ = "')
    first_import_at = source.index("\nfrom .")
    assert version_at < first_import_at, "define __version__ before any import"


def test_surfaces_derive_the_version_instead_of_hardcoding_it():
    """Structural guard against the drift that caused the last audit finding.

    Each surface must import the single source rather than carry its own copy
    that silently goes stale on the next release bump.
    """
    for name in ("cli.py", "cli_enhanced.py", "control_plane/app.py", "app/__init__.py"):
        source = (SRC / name).read_text(encoding="utf-8")
        assert "from aegis import __version__" in source, name

    # No hardcoded version literal left in the surfaces that used to have one.
    assert 'version="1.0' not in (SRC / "control_plane" / "app.py").read_text(encoding="utf-8")
    assert '__version__ = "1.0' not in (SRC / "app" / "__init__.py").read_text(encoding="utf-8")


def test_unknown_api_path_returns_json_404_not_the_spa_shell():
    """An unmatched /api/* path is a client error, never an HTML page."""
    client = TestClient(create_app())

    for path in ("/api/not-a-real-route", "/api/tool-permissions/nope/nope", "/api"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.headers["content-type"].startswith("application/json"), path
        assert response.json() == {"error": "Not found"}


def test_spa_page_routes_still_serve_the_shell():
    """The scope of the fix above must not break client-side routing."""
    client = TestClient(create_app())
    response = client.get("/some/client/side/route")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
