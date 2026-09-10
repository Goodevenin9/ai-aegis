"""Drift guard: every native-plugin hook resolves the engine endpoint through
the unified AEGIS_ENGINE_ENDPOINT variable (#190).

The engine endpoint is HOP 1 (agent -> engine, local app or self-host). It is
NOT the Aegis cloud. This test fails if a hook is added/edited that reads
the legacy var without the unified var in front — the bug that would silently
leave a plugin un-pointable at a remote Terraform engine.
"""
from __future__ import annotations

import pathlib
import re

import pytest

PLUGINS = pathlib.Path(__file__).resolve().parents[3] / "src" / "aegis" / "plugins"

# JS hooks: any file that resolves a base URL from AEGIS_ENGINE_ENDPOINT
JS_HOOKS = sorted(
    p for p in PLUGINS.rglob("*.js")
    if "AEGIS_ENGINE_ENDPOINT || DEFAULT_BASE_URL" in p.read_text(encoding="utf-8")
)

UNIFIED_JS = re.compile(
    r"process\.env\.AEGIS_ENGINE_ENDPOINT\s*\|\|\s*DEFAULT_BASE_URL"
)


def test_js_hooks_present():
    # Sanity: we actually found the hook files (guards against a path typo
    # making the parametrized test vacuously pass).
    assert len(JS_HOOKS) >= 20, f"expected >=20 hook files, found {len(JS_HOOKS)}"


@pytest.mark.parametrize("hook", JS_HOOKS, ids=lambda p: str(p.relative_to(PLUGINS)))
def test_js_hook_uses_unified_engine_endpoint(hook):
    src = hook.read_text(encoding="utf-8")
    assert UNIFIED_JS.search(src), (
        f"{hook.relative_to(PLUGINS)} resolves a base URL but not via "
        f"AEGIS_ENGINE_ENDPOINT || DEFAULT_BASE_URL"
    )


def test_openclaw_config_prefers_engine_endpoint():
    cfg = (PLUGINS / "openclaw" / "config.ts").read_text(encoding="utf-8")
    # unified var must appear, and before the legacy AEGIS_URL in the
    # url resolution chain.
    assert "AEGIS_ENGINE_ENDPOINT" in cfg
    # the resolution line (not the `url: string` interface decl) — it reads from
    # the environment.
    url_line = next(
        l for l in cfg.splitlines()
        if l.strip().startswith("url:") and "process.env" in l
    )
    assert url_line.index("AEGIS_ENGINE_ENDPOINT") < url_line.index("AEGIS_URL"), (
        "openclaw must prefer AEGIS_ENGINE_ENDPOINT over the legacy AEGIS_URL"
    )
