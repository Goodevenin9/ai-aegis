"""
Aegis local backend — bare API server for the frontend demo.

The demo frontend (aegis_demo_server.py on :8088) proxies /api/* to the real
backend on 127.0.0.1:8741 so the pages render live data. This launcher runs
THAT backend from source without the desktop window or the auto-opened browser
that `aegis-app --web` triggers — just FastAPI/uvicorn on 8741.

Requires PYTHONPATH to include the repo's src/ (the `aegis` package), e.g.:
    PYTHONPATH=<repo>/src py -3 i18n-build/aegis_backend_server.py
"""
import os
import sys

import uvicorn

# Run directly from a source checkout without requiring callers to mutate
# PYTHONPATH.  This launcher is the documented demo entry point.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aegis.app.server.app import create_app

HOST = "127.0.0.1"
PORT = 8741

if __name__ == "__main__":
    app = create_app(host=HOST, port=PORT)
    print(f"Aegis backend API on http://{HOST}:{PORT}/docs (DB inits on startup)")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info", timeout_graceful_shutdown=1)
