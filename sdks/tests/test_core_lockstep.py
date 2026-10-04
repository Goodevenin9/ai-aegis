"""The vendored ``_core.py`` copies must stay byte-identical to the source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "_core" / "aegis_sdk_core.py"


def test_core_copies_are_in_lockstep():
    canonical = SOURCE.read_bytes()
    copies = sorted(ROOT.glob("aegis-sdk-*/aegis_sdk_*/_core.py"))
    assert len(copies) == 4, f"expected 4 SDK packages, found {len(copies)}"
    for copy in copies:
        assert copy.read_bytes() == canonical, (
            f"{copy.relative_to(ROOT)} drifted from the core; run: python sdks/sync_core.py"
        )
