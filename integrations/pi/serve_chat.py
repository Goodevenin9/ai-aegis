#!/usr/bin/env python3
"""Aegis x pi 聊天界面的独立启动器（开发/演示用）。

它只托管 `backend/aegis_guide_ws.py` 里的路由（WebSocket 桥 + 静态前端），
不影响 Aegis 主应用。Aegis 应用本身仍需在 `AEGIS_BASE_URL`（默认 8741）上运行。

用法：
    python integrations/pi/serve_chat.py --port 8790
然后浏览器打开：
    http://127.0.0.1:8790/api/aegis-guide/chat

环境变量（透传给 pi 子进程）：
    AEGIS_BASE_URL / AEGIS_UI_TOKEN / AEGIS_APPROVER /
    AEGIS_SESSION_CAPABILITIES / AEGIS_PI_MODEL / AEGIS_PI_TOKEN ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让 `integrations.pi.backend...` 可导入（仓库根目录）
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI  # noqa: E402

from integrations.pi.backend.aegis_guide_ws import router  # noqa: E402

app = FastAPI(title="Aegis × pi chat", version="1.0.0")
app.include_router(router)


@app.get("/", include_in_schema=False)
async def _root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/api/aegis-guide/chat")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Aegis × pi chat UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
