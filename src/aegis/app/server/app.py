"""
FastAPI application for the Aegis local API server.

Provides REST API endpoints for:
- Threat analysis
- Threat intel queries
- Rules management
- Statistics
- Settings
- Static web UI files
"""

import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from aegis.app import __version__

logger = logging.getLogger(__name__)

# Path to web assets
WEB_ASSETS_PATH = Path(__file__).parent.parent / "assets" / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events, including database initialization.
    """
    logger.info("API server starting up...")

    # Initialize database and run migrations
    from aegis.app.database.connection import get_database
    from aegis.app.database.migrations import init_database_schema

    db = get_database()
    await db.connect()
    await init_database_schema(db)
    logger.info("Database initialized")

    # The five-stage runtime can operate in memory during isolated tests, but
    # the desktop application always attaches its durable state/event adapter.
    from aegis.app.server.routes.runtime_pipeline import configure_runtime_repository
    configure_runtime_repository(db)
    from aegis.app.server.routes.security_operations import configure_security_operations
    configure_security_operations(db)

    # Apply aegis.yml config (creates default if missing)
    from aegis.app.utils.config_file import apply_config_to_db, load_config
    await apply_config_to_db(db)

    # Detection readiness is a startup invariant. Loading lazily on the first
    # scan made /health claim zero rules and allowed stale cached rule IDs to
    # survive until traffic arrived.
    from aegis.app.services.analysis_service import init_analysis_service
    analysis_service = await init_analysis_service()
    logger.info("Detection engine ready: %s", await analysis_service.get_stats())

    # Auto-start proxy if configured in aegis.yml
    # For OpenClaw/ClawdBot: proxy only starts when block_mode is enabled
    # (plugin-only mode handles monitoring without proxy overhead).
    # For other integrations (langchain, crewai, ollama): proxy starts as before.
    try:
        import os as _os
        _cfg = load_config()
        _proxy_cfg = _cfg.get("proxy", {})
        _proxy_mode = _proxy_cfg.get("mode", "")
        _integration = _proxy_cfg.get("integration", "openclaw")
        _security_cfg = _cfg.get("security", {})
        _block_mode = bool(_security_cfg.get("block_mode", False))

        if _proxy_mode in ("multi-provider", "single"):
            _needs_proxy = True
            # OpenClaw/ClawdBot: plugin handles monitoring (threat scanning,
            # cost tracking, context injection). Proxy handles blocking
            # (tool stripping, threat blocking) when block_mode is enabled.
            if _integration in ("openclaw", "clawdbot"):
                _needs_proxy = _block_mode
                if not _block_mode:
                    logger.info(
                        "[aegis config] OpenClaw integration in monitor mode — "
                        "plugin handles monitoring, proxy not started. "
                        "Enable block_mode in aegis.yml to start the proxy for active blocking."
                    )

            if _needs_proxy:
                from aegis.app.server.routes.proxy import auto_start_from_config
                # Use AEGIS_PROXY_PORT (set by main.py from --port + 1) rather than the
                # aegis config default of 8742, so the proxy respects the --port flag.
                _proxy_port = int(_os.environ.get('AEGIS_PROXY_PORT', _proxy_cfg.get("port", 8742)))
                auto_start_from_config(
                    integration=_integration,
                    mode=_proxy_mode,
                    host=_proxy_cfg.get("host", "127.0.0.1"),
                    port=_proxy_port,
                    provider=_proxy_cfg.get("provider") or None,
                )
    except Exception as _e:
        logger.warning(f"Could not auto-start proxy from aegis.yml: {_e}")

    # Start the external SIEM forwarder. Runs unconditionally —
    # customers without Aegis Cloud still use SIEM export to
    # their own Splunk / Datadog / OTLP / webhook destinations.
    try:
        from aegis.app.services.external_forwarder import start_external_forwarder
        await start_external_forwarder()
    except Exception as _e:
        logger.warning(f"Could not start external_forwarder: {_e}")

    # Register the pre-uninstall backstop (#112). Idempotent. Emits
    # device.lifecycle.uninstalling to enrollment-sourced destinations on a
    # hard process exit that bypasses the graceful lifespan shutdown below.
    try:
        from aegis.app.services.device_lifecycle import register_preuninstall_hook
        register_preuninstall_hook()
    except Exception as _e:
        logger.warning(f"Could not register pre-uninstall hook: {_e}")

    # Start the cloud-sync long-poll loop ONLY if this device is enrolled
    # against an org. No-op for personal-mode / never-enrolled installs —
    # zero cloud calls in that case (per acceptance criteria #8).
    try:
        from aegis.app.services.cloud_sync import maybe_start_cloud_sync
        await maybe_start_cloud_sync(db)
    except Exception as _e:
        logger.warning(f"Could not start cloud_sync: {_e}")

    yield
    logger.info("API server shutting down...")

    # Pre-teardown lifecycle hook (#112): emit a device.lifecycle.uninstalling
    # OCSF event to any enrollment-sourced destinations BEFORE we stop the
    # forwarder, so the managing org sees the device check out. No-op for
    # personal / never-enrolled installs (no enrollment-sourced destinations).
    # Best-effort with a short ack timeout — a slow/unreachable cloud must
    # never wedge shutdown.
    try:
        from aegis.app.services.device_lifecycle import (
            LIFECYCLE_UNINSTALLING,
            emit_lifecycle_to_enrollment_destinations,
            mark_uninstall_emitted,
        )
        await emit_lifecycle_to_enrollment_destinations(LIFECYCLE_UNINSTALLING)
        # Tell the atexit backstop we already emitted, so it won't double-fire.
        mark_uninstall_emitted()
    except Exception as _e:
        logger.warning(f"Could not emit device.lifecycle.uninstalling cleanly: {_e}")

    try:
        from aegis.app.services.cloud_sync import stop_cloud_sync
        await stop_cloud_sync()
    except Exception as _e:
        logger.warning(f"Could not stop cloud_sync cleanly: {_e}")

    try:
        from aegis.app.services.external_forwarder import stop_external_forwarder
        await stop_external_forwarder()
    except Exception as _e:
        logger.warning(f"Could not stop external_forwarder cleanly: {_e}")


def create_app(host: str = "127.0.0.1", port: int = 8741) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        host: Server host address (used for CORS configuration).
        port: Server port (used for CORS configuration).

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Aegis Local Threat Monitor API",
        description=(
            "Local API for the Aegis Threat Monitor Desktop Application. "
            "Provides threat analysis for autonomous AI agents running locally."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Build allowed origins based on configured host/port
    # Restrict to localhost only for security (prevents malicious websites from accessing API)
    allowed_origins = [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]
    # If host is 0.0.0.0, still only allow localhost origins for CORS
    # (the API will be network-accessible but CORS blocks cross-origin browser requests)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Api-Key", "Authorization"],
    )

    # --- Inbound ingress-token enforcement (#190, engine v4.9.0+) ----------
    # When AEGIS_INGRESS_TOKEN is set (e.g. by the Terraform self-host
    # modules' `ingress_token` var), the engine requires it on EVERY request,
    # presented as `Authorization: Bearer <token>` or `X-Api-Key: <token>`.
    # Empty/unset = no app-layer gate (rely on network gating: a private
    # subnet / ingress_cidrs). `/health` stays open for the load-balancer
    # probe; CORS preflight (OPTIONS) is exempt. Constant-time comparison
    # avoids token timing leaks. This is the inbound counterpart to the
    # SDK/plugin AEGIS_ENGINE_ENDPOINT forwarding — it closes the auth
    # loop for a publicly-exposed self-host endpoint. The env var is read per
    # request so the gate reflects the current deployment config.
    _INGRESS_OPEN_PATHS = frozenset({"/health", "/api/system/environment"})

    @app.middleware("http")
    async def _enforce_ingress_token(request: Request, call_next):
        expected = os.environ.get("AEGIS_INGRESS_TOKEN", "").strip()
        if (
            expected
            and request.method != "OPTIONS"
            and request.url.path not in _INGRESS_OPEN_PATHS
        ):
            presented = ""
            authz = request.headers.get("authorization", "")
            if authz[:7].lower() == "bearer ":
                presented = authz[7:].strip()
            if not presented:
                presented = request.headers.get("x-api-key", "").strip()
            if not (presented and hmac.compare_digest(presented, expected)):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

    # SPA fallback — serve index.html for any 404 on a GET request that isn't an API call
    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc):
        path = request.url.path
        if request.method == "GET" and not path.startswith("/api") and not path.startswith("/docs") and not path.startswith("/redoc"):
            index_path = WEB_ASSETS_PATH / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Health check endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        """Check server and database health."""
        from aegis.app.database.connection import get_database

        try:
            db = get_database()
            db_health = await db.health_check()
        except Exception:
            logger.exception("Database health check failed")
            db_health = {
                "connected": False,
                "error": "Database health check failed",
            }

        status = "healthy" if db_health.get("connected") else "degraded"

        try:
            from aegis.app.services.analysis_service import get_analysis_service
            rule_stats = await get_analysis_service().get_stats()
        except Exception:
            logger.exception("Rule readiness check failed")
            rule_stats = {"community_rules": 0, "custom_rules": 0, "compiled_patterns": 0}

        return {
            "status": status,
            "version": __version__,
            "database": db_health,
            "rules_loaded": {
                "community": rule_stats.get("community_rules", 0),
                "custom": rule_stats.get("custom_rules", 0),
                "compiled_patterns": rule_stats.get("compiled_patterns", 0),
            },
        }

    # Device identity — used by the audit UI to display which machine
    # the chain belongs to. Returns the stable per-device ID derived
    # from the OS machine identifier (hashed + namespaced — raw OS
    # UUID is never transmitted).
    @app.get("/api/system/device-id", tags=["System"])
    async def get_device():
        from aegis.app.utils.device_id import get_device_id
        return {"device_id": get_device_id()}

    # Runtime environment — lets the UI adapt when the app is running headless
    # in a container (self-host / Terraform engine image) instead of as the
    # local desktop app. When containerized, "monitor THIS device" is
    # meaningless (the box is the engine, not where agents run), so the
    # Connect-Agents page hides that option and shows only the self-host steps,
    # pre-pointing agents at this engine's URL.
    @app.get("/api/system/environment", tags=["System"])
    async def get_environment():
        def _in_container() -> bool:
            if os.environ.get("AEGIS_CONTAINER", "").strip().lower() in ("1", "true", "yes"):
                return True
            if os.path.exists("/.dockerenv"):
                return True
            try:
                with open("/proc/1/cgroup", "rt") as fh:
                    cgroups = fh.read()
                if any(marker in cgroups for marker in ("docker", "containerd", "kubepods")):
                    return True
            except Exception:
                pass
            return False

        public_url = (
            os.environ.get("AEGIS_PUBLIC_URL")
            or os.environ.get("AEGIS_BASE_URL")
            or os.environ.get("AEGIS_ENGINE_ENDPOINT")
            or ""
        ).strip().rstrip("/")
        import platform
        _os_friendly = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}
        in_container = _in_container()
        # Authoritative runtime posture the whole UI keys off of. "endpoint" =
        # this process is a self-hosted engine (containerized OR reachable at a
        # configured public URL), so agents point AT it over the network and the
        # local-desktop install steps don't apply. "local" = the desktop app the
        # user runs on the same machine as their agents.
        mode = "endpoint" if (in_container or public_url) else "local"
        return {
            "in_container": in_container,
            "public_url": public_url or None,
            "mode": mode,
            "ingress_token_required": bool(os.environ.get("AEGIS_INGRESS_TOKEN", "").strip()),
            "os": _os_friendly.get(platform.system(), platform.system() or "Unknown"),
        }

    # Register route modules
    from aegis.app.server.routes import (
        analyze,
        rules,
        cloud_settings,
        threat_analytics,
        threat_intel,
        llm,
        proxy,
        tool_permissions,
        jit_access,
        egress,
        costs,
        hooks,
        hooks_claude_code,
        hooks_codex,
        hooks_copilot_cli,
        hooks_cursor,
        hooks_hermes,
        skill_scans,
        skill_permissions,
        siem_forwarders,
        device_admin,
        redactions,
        runtime_pipeline,
        security_operations,
    )

    # Quick analysis endpoint (uses X-Api-Key for cloud)
    app.include_router(analyze.router, prefix="", tags=["Analysis"])

    # Primary API - mirrors cloud API structure
    app.include_router(threat_analytics.router, prefix="/api", tags=["Threat Analytics"])
    app.include_router(threat_intel.router, prefix="/api", tags=["Threat Intel"])
    app.include_router(rules.router, prefix="/api", tags=["Rules"])
    app.include_router(cloud_settings.router, prefix="/api", tags=["Cloud Settings"])
    app.include_router(llm.router, prefix="/api", tags=["LLM Review"])
    app.include_router(proxy.router, prefix="/api", tags=["Proxy"])
    app.include_router(tool_permissions.router, prefix="/api", tags=["Tool Permissions"])
    app.include_router(jit_access.router, prefix="/api", tags=["JIT Access"])
    app.include_router(egress.router, prefix="/api", tags=["Egress Governance"])
    app.include_router(costs.router, prefix="/api", tags=["Costs"])
    app.include_router(hooks.router, prefix="/api", tags=["Hooks"])
    app.include_router(hooks_claude_code.router, prefix="/api", tags=["Hooks"])
    app.include_router(hooks_codex.router, prefix="/api", tags=["Hooks"])
    app.include_router(hooks_copilot_cli.router, prefix="/api", tags=["Hooks"])
    app.include_router(hooks_cursor.router, prefix="/api", tags=["Hooks"])
    app.include_router(hooks_hermes.router, prefix="/api", tags=["Hooks"])
    app.include_router(skill_scans.router, prefix="/api", tags=["Skill Scanner"])
    app.include_router(skill_permissions.router, prefix="/api", tags=["Skill Permissions"])
    app.include_router(siem_forwarders.router, prefix="/api", tags=["SIEM Forwarders"])
    # active-mcp-and-policy-sync — device admin (POST /api/system/device-id/reset)
    app.include_router(device_admin.router, prefix="/api", tags=["Device Admin"])
    # Redactions audit log — backs the local Redactions page (v4.3+).
    app.include_router(redactions.router, prefix="/api", tags=["Redactions"])
    # Five-stage semantic session pipeline. DeepSeek is used only by the
    # intent observer; the PreToolUse decision endpoint is deterministic.
    app.include_router(runtime_pipeline.router, prefix="/api", tags=["Runtime Pipeline"])
    app.include_router(
        security_operations.router, prefix="/api", tags=["Security Operations Agent"]
    )
    # Bundle 0.4 — Agent Replay Timeline. Merged threat / tool-audit / cost feed.
    from aegis.app.server.routes import replay
    app.include_router(replay.router, prefix="/api", tags=["Replay"])
    # active-agent-observability #143 — Agent–Tool Live Graph (agent→tool node map).
    from aegis.app.server.routes import graph
    app.include_router(graph.router, prefix="/api", tags=["Graph"])
    # active-agent-observability #142 — Agent Run Trace (runs → spans waterfall).
    from aegis.app.server.routes import traces
    app.include_router(traces.router, prefix="/api", tags=["Traces"])
    # Local detection — what harnesses/sessions/agents are running on this device.
    from aegis.app.server.routes import detection
    app.include_router(detection.router, prefix="/api", tags=["Detection"])
    # conversion-ux — Instant Agent Audit (opt-in retroactive transcript scan).
    from aegis.app.server.routes import instant_audit
    app.include_router(instant_audit.router, prefix="/api", tags=["Instant Audit"])

    # 小瑷（Aeg）— 对话式安全助手：挂载 pi RPC 的 WebSocket 桥与聊天前端
    # （/api/aegis-guide/chat、/api/aegis-guide/ws）。仅当从源码仓库运行时可用；
    # `integrations/` 随仓库分发，安装版找不到则静默跳过，不影响主应用。
    try:  # noqa: SIM105
        import sys as _sys
        from pathlib import Path as _Path

        _repo_root = _Path(__file__).resolve().parents[4]
        _bridge = _repo_root / "integrations" / "pi" / "backend" / "aegis_guide_ws.py"
        if _bridge.is_file():
            if str(_repo_root) not in _sys.path:
                _sys.path.insert(0, str(_repo_root))
            from integrations.pi.backend.aegis_guide_ws import (
                router as aegis_guide_router,
            )

            app.include_router(aegis_guide_router)
    except Exception:  # pragma: no cover - optional integration
        pass

    # Serve web UI static files
    if WEB_ASSETS_PATH.exists():
        # Mount static directories
        css_path = WEB_ASSETS_PATH / "css"
        js_path = WEB_ASSETS_PATH / "js"
        icons_path = WEB_ASSETS_PATH / "icons"

        if css_path.exists():
            app.mount("/css", StaticFiles(directory=str(css_path)), name="css")
        if js_path.exists():
            app.mount("/js", StaticFiles(directory=str(js_path)), name="js")
        if icons_path.exists():
            app.mount("/icons", StaticFiles(directory=str(icons_path)), name="icons")

        # Mount images directory
        images_path = WEB_ASSETS_PATH / "images"
        if images_path.exists():
            app.mount("/images", StaticFiles(directory=str(images_path)), name="images")

        # Mount self-hosted fonts (v5 type signature). Bundled OFL-licensed
        # faces served in-process so the CSP `font-src 'self'` is satisfied and
        # the type identity works fully offline (no external font CDN).
        fonts_path = WEB_ASSETS_PATH / "fonts"
        if fonts_path.exists():
            app.mount("/fonts", StaticFiles(directory=str(fonts_path)), name="fonts")

        # Mount SIEM dashboard templates (Sentinel workbook, Splunk XML).
        # Ship with the package; served in-process so the Copy / Download
        # modal on the SIEM Forwarder page works offline and doesn't
        # depend on a public GitHub URL.
        siem_templates_path = WEB_ASSETS_PATH / "siem-templates"
        if siem_templates_path.exists():
            app.mount("/siem-templates", StaticFiles(directory=str(siem_templates_path)), name="siem-templates")

        _NO_CACHE_HEADERS = {
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        }

        # Serve index.html at root
        @app.get("/", include_in_schema=False)
        async def serve_index():
            index_path = WEB_ASSETS_PATH / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path), headers=_NO_CACHE_HEADERS)
            return {"error": "Web UI not found"}

        # Client-side routing catch-all — serve index.html for any unmatched path.
        # FastAPI matches registered API routes first; this only fires for SPA
        # page routes. An unmatched /api/* path is a client error, NOT a page
        # route: returning the HTML shell with HTTP 200 makes every API consumer
        # parse HTML (and shows up as a JSONDecodeError instead of a clean 404).
        @app.get("/{path:path}", include_in_schema=False)
        async def serve_spa(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"error": "Not found"}, status_code=404)
            index_path = WEB_ASSETS_PATH / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path), headers=_NO_CACHE_HEADERS)
            return {"error": "Web UI not found"}

        logger.info(f"Web UI mounted from {WEB_ASSETS_PATH}")

    logger.info("FastAPI application created")
    return app
