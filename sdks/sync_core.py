#!/usr/bin/env python3
"""Copy the canonical core into every SDK package as ``_core.py``.

Each ``aegis_sdk_<framework>`` package is self-contained (so
``pip install aegis-sdk-<framework> --no-deps`` works), which means the core
is vendored. This script is the only sanctioned way to update those copies;
``tests/test_core_lockstep.py`` fails if they drift.

Usage:
    python sdks/sync_core.py            # write copies
    python sdks/sync_core.py --check    # exit 1 if any copy is stale
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "_core" / "aegis_sdk_core.py"
PACKAGE_DIRS = sorted(ROOT.glob("aegis-sdk-*"))


def _targets() -> list[Path]:
    out = []
    for pkg in PACKAGE_DIRS:
        mod = pkg / pkg.name.replace("-", "_")
        if mod.is_dir():
            out.append(mod / "_core.py")
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    canonical = SOURCE.read_bytes()
    digest = hashlib.sha256(canonical).hexdigest()[:12]
    stale: list[Path] = []
    for target in _targets():
        current = target.read_bytes() if target.exists() else b""
        if current == canonical:
            continue
        stale.append(target)
        if not check:
            target.write_bytes(canonical)
    if check:
        for t in stale:
            print(f"STALE: {t.relative_to(ROOT)}")
        if stale:
            print(f"\n{len(stale)} copy(ies) out of sync with core {digest}. Run: python sdks/sync_core.py")
            return 1
        print(f"all {len(_targets())} copies match core {digest}")
        return 0
    for t in stale:
        print(f"synced: {t.relative_to(ROOT)}")
    if not stale:
        print("already in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
