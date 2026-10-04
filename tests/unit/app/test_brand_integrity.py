"""Product identity regression checks for the AI Aegis distribution."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

# Apache-2.0 attribution is intentionally retained in these legal artifacts.
LEGAL_PATHS = {
    ROOT / "LICENSE",
    ROOT / "NOTICE",
    ROOT / "src" / "aegis" / "rules" / "RULES_ATTRIBUTION.md",
    ROOT / "src" / "aegis" / "rules" / "tool_permissions" / "RULES_ATTRIBUTION.md",
}

# Third-party comparison documents name competitors on purpose — that is the
# document's subject, not leaked product identity. Excluded from the identity
# scan so the comparison can cite rival products by name.
THIRD_PARTY_COMPARISON_PATHS = {
    ROOT / "docs" / "COMPETITOR_BENCHMARK_COMPARISON.md",
}

RUNTIME_ROOTS = (
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "installers",
    ROOT / "i18n-build",
    ROOT / "docs",
    ROOT / "deploy",
    ROOT / "tests",
    ROOT / ".github",
    ROOT / ".claude-plugin",
)


def _product_files():
    for root in RUNTIME_ROOTS:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or any(part.endswith(".egg-info") for part in path.parts)
            ):
                continue
            if path.suffix.lower() in {".pyc", ".png", ".ico", ".woff", ".woff2", ".svg"}:
                continue
            yield path
    for path in (
        ROOT / "setup.py",
        ROOT / "Dockerfile.engine",
        ROOT / "Dockerfile.mcp",
        ROOT / "Dockerfile.control-plane",
        ROOT / "Dockerfile.demo",
        ROOT / "docker-compose.self-host.yml",
        ROOT / "docker-compose.demo.yml",
        ROOT / "docker-compose.nginx.yml",
        ROOT / "docker-entrypoint.sh",
        ROOT / ".env.self-host.example",
    ):
        if path.exists():
            yield path


def test_runtime_and_plugins_have_no_legacy_product_identity():
    failures: list[str] = []
    forbidden = (
        "secure" + "vector",
        "secure" + "-vector",
        "aegis" + ".example",
        "wanshang" + "hao",
        "s" + "vgrad",
    )
    for path in _product_files():
        if (
            path == Path(__file__)
            or path in LEGAL_PATHS
            or path in THIRD_PARTY_COMPARISON_PATHS
            or path.name == "LICENSE"
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            # Upstream copyright lines are legally required attribution, not
            # product identity exposed by the application.
            if "copyright" in lowered:
                continue
            legacy_short = "s" + "v"
            legacy_prefix = legacy_short + "_"
            if (
                any(token in lowered for token in forbidden)
                or re.search(r"(?<![A-Z])SV_[A-Z0-9_]+", line)
                or re.search(rf"(?<![A-Za-z0-9]){legacy_prefix}[a-z0-9_]+", lowered)
                or re.search(rf"(?i)(?<![A-Za-z0-9]){legacy_short}(?:[-.]|\b)", line)
                or re.search(rf"(?i)(?:[-._]){legacy_short}(?![A-Za-z])", line)
                or re.search(rf"(?<![A-Za-z0-9]){legacy_short}(?=[A-Z])", line)
                or re.search(rf"(?<![A-Za-z0-9]){legacy_short.upper()}(?=[A-Z][a-z])", line)
                or re.search(rf"{legacy_short.title()}(?=[A-Z])", line)
            ):
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert not failures, "Legacy identity remains:\n" + "\n".join(failures[:80])


def test_product_file_names_have_no_legacy_prefix():
    failures = [
        str(path.relative_to(ROOT))
        for root in RUNTIME_ROOTS
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not any(part.endswith(".egg-info") for part in path.parts)
        and path.name.lower().startswith(("s" + "v_", "secure" + "vector"))
    ]
    assert not failures, "Legacy filenames remain:\n" + "\n".join(failures)
