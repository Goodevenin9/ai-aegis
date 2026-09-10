"""Command-line entry point for the AI Aegis control plane."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("AEGIS_CONTROL_PLANE_HOST", "0.0.0.0")
    port = int(os.environ.get("AEGIS_CONTROL_PLANE_PORT", "8780"))
    uvicorn.run("aegis.control_plane.app:create_app", factory=True, host=host, port=port)


if __name__ == "__main__":
    main()
