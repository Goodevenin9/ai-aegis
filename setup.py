"""
Setup configuration for AI Threat Monitor
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from __init__.py
def get_version():
    version_file = os.path.join("src", "aegis", "__init__.py")
    # Pin the encoding: the file is UTF-8 and contains non-ASCII, so the
    # platform default (e.g. GBK on zh-CN Windows) raises UnicodeDecodeError.
    with open(version_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "1.0.0"

setup(
    name="ai-aegis",
    version=get_version(),
    author="Aegis Team",
    # author_email removed - contact via Gitee issues
    description="Real-time AI threat monitoring. Protect your apps from prompt injection, leaks, and attacks in just a few lines of code.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitee.com/wan-xianghao/ai-aegis",
    # Kept alongside the "License :: OSI Approved :: Apache Software License"
    # classifier below, which is what PyPI actually renders in the sidebar.
    # Note this lands in the legacy `License:` metadata field, NOT in
    # `License-Expression`: a setup.py-only build does not get PEP 639
    # treatment from setuptools (that needs a [project] table). Switching to
    # `License-Expression` is a separate change to pyproject.toml.
    license="Apache-2.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",  # Base SDK supports 3.9+; MCP extras require 3.10+
    install_requires=[
        "PyYAML>=5.1",
        "requests>=2.32.4",  # Security fix for CVE-2025-47083 (insecure temp file reuse)
        "aiohttp>=3.13.5",  # Security fixes for duplicate Host headers, SSRF, header injection, and DoS vulnerabilities
        "typing-extensions>=4.0.0",
        "urllib3>=2.6.3",  # Security fix for CVE-2025-66418, CVE-2025-66471, CVE-2026-21441 (decompression bombs)
    ],
    extras_require={
        "mcp": [
            # NOTE: MCP dependencies require Python >=3.10
            # The base package works with 3.9+, but [mcp] extras need 3.10+
            #
            # aegis.mcp.auth_validator imports httpx directly. mcp 2.x /
            # fastmcp 4.x switched to httpx2 and no longer install httpx, so a
            # [mcp]-only install lost it and MCP detection failed closed.
            "httpx>=0.24.0",
            # The code targets the FastMCP surface exposed by mcp 1.x
            # (`mcp.server.fastmcp`) plus the standalone fastmcp 2.x package.
            # Cap the majors, or `>=` silently upgrades to mcp 2.x / fastmcp 4.x,
            # whose import surface changed.
            "mcp>=1.23.0,<2",  # Security fix for GHSA-c2jp-c369-7pvx (was >=0.1.0)
            "fastmcp>=2.13.0,<3",  # Security fix (was >=0.1.0)
        ],
        "app": [
            # Desktop application dependencies
            "pywebview>=5.0",  # Lightweight cross-platform webview
            "fastapi>=0.100.0",  # Local API server
            "uvicorn[standard]>=0.20.0",  # ASGI server
            "aiosqlite>=0.19.0",  # Async SQLite
            "sqlalchemy>=2.0.0",  # Database ORM
            "watchdog>=3.0.0",  # File watching for hot-reload
            "platformdirs>=3.0.0",  # Cross-platform paths
            "keyring>=23.0.0",  # Secure credential storage (OS keychain)
            "httpx>=0.24.0",  # Async HTTP client for cloud API
            "websockets>=12.0",  # WebSocket proxy for OpenClaw integration
            "langgraph>=1.2,<2; python_version >= '3.10'",  # P2 durable security Agent graph
            "python-multipart>=0.0.20",  # Bounded evidence uploads
            "pypdf>=6,<7",  # Security-policy PDF extraction
            "python-docx>=1.2,<2",  # DOCX security-policy extraction
            "Pillow>=11,<13",  # Safe image metadata/decoding for OCR
            "pytesseract>=0.3.13",  # Optional local screenshot OCR adapter
            # Pydantic + FastAPI evaluate route annotations at registration time
            # using ast-based union resolution; on 3.9 they need this backport to
            # handle PEP 604 `X | None` strings produced by `from __future__ import
            # annotations`. No-op on 3.10+.
            'eval_type_backport>=0.2.0; python_version<"3.10"',
        ],
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=3.0",
            "pytest-xdist>=2.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0",
            "flake8>=4.0",
            "isort>=5.0",
            "mypy>=0.900",
            "safety>=2.0",
            "bandit>=1.7",
            "psutil>=5.8",  # For benchmark memory tests
            "fastapi>=0.100.0",  # Required for FastAPI test client in unit tests
            "httpx>=0.24.0",     # Required by FastAPI TestClient
        ],
        "benchmark": [
            "psutil>=5.8",
            "memory-profiler>=0.60",
        ],
        "all": [
            # Same major caps as [mcp]: mcp 2.x / fastmcp 4.x changed the import
            # surface the code targets.
            "mcp>=1.23.0,<2",  # Security fix
            "fastmcp>=2.13.0,<3",  # Security fix
            "pywebview>=5.0",  # Lightweight cross-platform webview
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.20.0",
            "aiosqlite>=0.19.0",
            "sqlalchemy>=2.0.0",
            "watchdog>=3.0.0",
            "platformdirs>=3.0.0",
            "langgraph>=1.2,<2; python_version >= '3.10'",
            "python-multipart>=0.0.20",
            "pypdf>=6,<7",
            "python-docx>=1.2,<2",
            "Pillow>=11,<13",
            "pytesseract>=0.3.13",
            "psutil>=5.8",
            "memory-profiler>=0.60",
            'eval_type_backport>=0.2.0; python_version<"3.10"',
        ],
        "control-plane": [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.20.0",
        ],
        "demo": [
            # Headless web demo: the visible P2 features must be executable,
            # not mock cards. Desktop/keyring/watchdog dependencies remain out.
            "fastapi>=0.100.0",
            "uvicorn>=0.20.0",
            "aiosqlite>=0.19.0",
            "sqlalchemy>=2.0.0",
            "platformdirs>=3.0.0",
            "httpx>=0.24.0",
            "python-multipart>=0.0.20",
            "langgraph>=1.2,<2; python_version >= '3.10'",
            "pypdf>=6,<7",
            "python-docx>=1.2,<2",
            "Pillow>=11,<13",
            "pytesseract>=0.3.13",
        ],
    },
    include_package_data=True,
    data_files=[
        (
            "aegis/benchmarks",
            [
                "benchmarks/chinese_agent_security_p1.jsonl",
                "benchmarks/developer_workflows_v1.jsonl",
            ],
        ),
    ],
    package_data={
        "aegis": [
            "rules/**/*.yml",
            "rules/**/*.yaml",
            "rules/*.md",
            "rules/README.md",
            "rules/RULES_ATTRIBUTION.md",
            "rules/LICENSE_NOTICE.md",
            "pricing/*.yml",
            "app/assets/**/*",
            "app/assets/web/**/*",
            "app/assets/web/css/*",
            "app/assets/web/js/**/*",
            "app/assets/web/icons/*",
            "plugins/openclaw/*",
            "plugins/claude-code/**/*",
            # setuptools' `**/*` glob skips dot-prefixed dirs — list .claude-plugin/
            # explicitly so plugin.json (the file Claude Code reads to discover
            # the plugin) actually ships in the wheel.
            "plugins/claude-code/.claude-plugin/*",
            "plugins/codex/**/*",
            # Same dot-dir gotcha as above — list .codex-plugin/ explicitly
            # so plugin.json (the file Codex reads on plugin add) ships.
            "plugins/codex/.codex-plugin/*",
            # Copilot CLI plugin — manifest is plugin.json at the tree root
            # (no dot-dir), so the recursive glob covers everything.
            "plugins/copilot-cli/**/*",
            # Cursor plugin — manifest is .cursor-plugin/plugin.json (the file
            # Cursor reads to discover the local plugin). Same dot-dir gotcha as
            # claude-code/codex: setuptools `**/*` skips dot-dirs, so list it
            # explicitly or the wheel ships the plugin without its manifest.
            "plugins/cursor/**/*",
            "plugins/cursor/.cursor-plugin/*",
            "guardian/model.runtime.json.gz",
            "guardian/model.runtime.json.gz.sha256",
        ],
        "": ["NOTICE"],
    },
    entry_points={
        "console_scripts": [
            "aegis=aegis.cli:main",
            "aegis-monitor=aegis.cli:main",
            "aegis-mcp=aegis.mcp.__main__:sync_main",
            "aegis-app=aegis.app.main:main",
            "aegis-proxy=aegis.integrations.openclaw_llm_proxy:main",
            "aegis-control-plane=aegis.control_plane.__main__:main",
        ],
    },
    keywords="ai security llm prompt-injection threat-detection threat-monitoring openai claude aegis",
    project_urls={
        "Bug Reports": "https://gitee.com/wan-xianghao/ai-aegis/issues",
        "Source": "https://gitee.com/wan-xianghao/ai-aegis",
        "Documentation": "https://gitee.com/wan-xianghao/ai-aegis/tree/master/docs",
        "Homepage": "https://gitee.com/wan-xianghao/ai-aegis",
    },
)
