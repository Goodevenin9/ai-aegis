"""Boot the Aegis app (+ optional LLM proxy) and run the live integration tests.

The integration-marked tests under ``tests/`` assume real services:

- a running Aegis app on ``127.0.0.1:8741`` (``AEGIS_WEB_PORT``), and
- for the cost / tool-permission live cases, the LLM proxy on
  ``127.0.0.1:8742`` (``AEGIS_PROXY_PORT``).

``pyproject.toml`` excludes them from the default ``pytest tests/`` run via
``-m "not integration"``, so nothing in CI exercised them. This script makes
that reproducible locally and in CI: it starts the services, waits until they
are listening, runs the selected tests, and always tears the children down.

Usage::

    # Plugin → hook → API → policy path (self-contained, fast). Default.
    python scripts/run_live_integration.py

    # Everything that needs the app + proxy (slower; see KNOWN FAILURES below).
    python scripts/run_live_integration.py --with-proxy

    # A specific selection.
    python scripts/run_live_integration.py tests/test_tool_audit_log_live.py

KNOWN FAILURES (as of the 1.0.3 work): the ``--with-proxy`` selection is not
green yet — ``tests/unit/app/test_costs_budget.py`` and the ``*_live.py``
suites have pre-existing expectation/state issues that need a dedicated pass.
The plugin E2E default selection IS green and is the one wired into CI.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "tmp" / "live-integration"

DEFAULT_TESTS = [
    "tests/integration/test_claude_code_plugin_e2e.py",
    "tests/integration/test_codex_plugin_e2e.py",
]
PROXY_TESTS = DEFAULT_TESTS + [
    "tests/unit/app/test_costs_budget.py",
    "tests/test_tool_audit_log_live.py",
    "tests/test_tool_permissions_api_live.py",
]


def _src_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _wait_http(host: str, port: int, path: str, timeout: float = 90.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=3) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def _wait_port(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(1.0)
    return False


def _spawn(name: str, args: list[str]) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"{name}.log", "w", encoding="utf-8")  # noqa: SIM115 - closed on teardown
    proc = subprocess.Popen(args, cwd=str(ROOT), env=_src_env(), stdout=log, stderr=subprocess.STDOUT)
    setattr(proc, "_aegis_log", log)
    return proc


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    log = getattr(proc, "_aegis_log", None)
    if log is not None:
        log.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-proxy", action="store_true", help="Also start the LLM proxy and run its live tests.")
    parser.add_argument("tests", nargs="*", help="Explicit test paths (defaults to the plugin E2E selection).")
    parser.add_argument("--timeout", type=float, default=90.0, help="Seconds to wait for /health.")
    args = parser.parse_args()

    host = "127.0.0.1"
    web_port = int(os.environ.get("AEGIS_WEB_PORT", "8741"))
    proxy_port = int(os.environ.get("AEGIS_PROXY_PORT", "8742"))
    tests = args.tests or (PROXY_TESTS if args.with_proxy else DEFAULT_TESTS)

    app: subprocess.Popen | None = None
    proxy: subprocess.Popen | None = None
    try:
        print(f"[live] starting app on {host}:{web_port}", flush=True)
        app = _spawn(
            "app",
            [sys.executable, "-m", "uvicorn", "aegis.app.server.app:create_app",
             "--factory", "--host", host, "--port", str(web_port), "--log-level", "warning"],
        )
        if not _wait_http(host, web_port, "/health", timeout=args.timeout):
            print("[live] app did not become healthy; see tmp/live-integration/app.log", file=sys.stderr)
            return 2

        if args.with_proxy:
            print(f"[live] starting proxy on {host}:{proxy_port}", flush=True)
            proxy = _spawn(
                "proxy",
                [sys.executable, "-m", "aegis.integrations.openclaw_llm_proxy",
                 "--provider", "openai", "--port", str(proxy_port)],
            )
            if not _wait_port(host, proxy_port, timeout=args.timeout):
                print("[live] proxy did not start; see tmp/live-integration/proxy.log", file=sys.stderr)
                return 2

        env = _src_env()
        env["AEGIS_WEB_PORT"] = str(web_port)
        env["AEGIS_PROXY_PORT"] = str(proxy_port)
        print(f"[live] running {len(tests)} test path(s) with -m integration", flush=True)
        return subprocess.call(
            [sys.executable, "-m", "pytest", *tests, "-m", "integration", "-q", "-p", "no:cacheprovider"],
            cwd=str(ROOT), env=env,
        )
    finally:
        _stop(proxy)
        _stop(app)
        print("[live] services stopped", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
