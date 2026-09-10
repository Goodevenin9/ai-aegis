"""Configuration for the self-hosted AI Aegis control plane."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ControlPlaneSettings:
    """Deployment settings loaded from explicit ``AEGIS_*`` variables."""

    database_path: Path
    admin_key: str
    public_url: str
    org_id: str
    org_name: str
    admin_email: str

    @classmethod
    def from_env(cls) -> "ControlPlaneSettings":
        admin_key = os.environ.get("AEGIS_CONTROL_PLANE_ADMIN_KEY", "").strip()
        if len(admin_key) < 16:
            raise RuntimeError(
                "AEGIS_CONTROL_PLANE_ADMIN_KEY must contain at least 16 characters"
            )
        return cls(
            database_path=Path(
                os.environ.get("AEGIS_CONTROL_PLANE_DB", "./data/control-plane.db")
            ).expanduser(),
            admin_key=admin_key,
            public_url=os.environ.get(
                "AEGIS_CONTROL_PLANE_URL", "http://127.0.0.1:8780"
            ).rstrip("/"),
            org_id=os.environ.get("AEGIS_ORG_ID", "org_local"),
            org_name=os.environ.get("AEGIS_ORG_NAME", "AI Aegis Organization"),
            admin_email=os.environ.get("AEGIS_ADMIN_EMAIL", "admin@localhost"),
        )
