"""Aegis × pi —— Web 前端桥（FastAPI 路由）

一个极薄的双向管道：浏览器 ⇄ WebSocket ⇄ `pi --mode rpc` 子进程。

- 浏览器发来的每一条 JSON 原样写进 pi 的 stdin（就是 pi RPC 命令）
- pi stdout 的每一行 JSONL 原样转发给浏览器（就是 pi RPC 事件）

因此前端直接说 pi RPC 协议，无需自定义协议。

挂载（在你现有 app.py 里加一行）：
    from integrations.pi.backend.aegis_guide_ws import router as aegis_guide_router
    app.include_router(aegis_guide_router)

环境变量：
    AEGIS_PI_BIN        默认 "pi"
    AEGIS_PI_EXTENSION  默认 <repo>/integrations/pi/aegis-guide.ts
    AEGIS_PI_MODEL      可选，如 "deepseek/deepseek-chat"
    AEGIS_PI_CWD        可选，pi 子进程工作目录
    AEGIS_PI_TOKEN      可选，WebSocket 鉴权（?token=... 或 X-Aegis-UI-Token）
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/aegis-guide", tags=["Aegis Guide"])

_EXT_DEFAULT = Path(__file__).resolve().parents[1] / "aegis-guide.ts"
_FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
_PROMPT_DEFAULT = Path(__file__).resolve().parents[1] / "prompts" / "xiaoai-system.md"


def _fetch_ui_token() -> str:
    """向本地 Aegis 取当前 UI token（每进程随机），让写操作工具立即可用。"""
    base = os.environ.get("AEGIS_BASE_URL", "http://127.0.0.1:8741").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/jit/ui-token", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8", "replace")).get("token", "")
    except Exception:  # noqa: BLE001 - best effort
        return ""


def _resolve_extension() -> str:
    return os.environ.get("AEGIS_PI_EXTENSION", str(_EXT_DEFAULT))


def _resolve_system_prompt() -> str:
    """小瑷的输出规范/system prompt 文件；缺省随仓库分发。"""
    return os.environ.get("AEGIS_PI_SYSTEM_PROMPT", str(_PROMPT_DEFAULT))


def _resolve_pi_bin() -> str:
    """解析 pi 可执行文件。

    Windows 上 npm 安装的是 `pi.CMD`；CreateProcess 对不带扩展名的 “pi”
    只会尝试 `.exe`，找不到 `.cmd`，因此必须用 shutil.which 解析出真实路径。
    """
    return os.environ.get("AEGIS_PI_BIN") or shutil.which("pi") or "pi"


def _session_dir() -> Path:
    """pi 按 cwd 编码的会话目录（与服务端会话列表对应）。

    规则（与 pi 的 session-manager 一致）：
        ~/.pi/agent/sessions/--<cwd 去掉首位分隔符、把 : / \\ 换成 ->--/
    """
    cwd = os.environ.get("AEGIS_PI_CWD") or os.getcwd()
    safe = "--" + re.sub(r"[/\\:]", "-", cwd.lstrip("/\\")) + "--"
    return Path.home() / ".pi" / "agent" / "sessions" / safe


def _read_session_info(path: Path) -> dict[str, Any]:
    """从 pi 会话文件提炼列表所需元数据（标题/时间/消息数）。"""
    title = ""
    count = 0
    try:
        raw = path.read_bytes()[: 512 * 1024]
    except OSError:
        raw = b""
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        kind = obj.get("type")
        if kind == "session_info" and obj.get("name"):
            title = str(obj["name"])
        elif kind == "message":
            msg = obj.get("message") or {}
            if msg.get("role") != "system":
                count += 1
            if not title and msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    title = content
                elif isinstance(content, list):
                    title = " ".join(
                        str(p.get("text", "")) for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
    title = re.sub(r"\s+", " ", title.strip())[:40]
    if not title:
        title = f"会话 {path.stem[:16]}"
    try:
        updated = int(path.stat().st_mtime * 1000)
    except OSError:
        updated = 0
    return {
        "id": path.stem.rsplit("_", 1)[-1],
        "name": path.name,
        "title": title,
        "messageCount": count,
        "sessionPath": str(path),
        "updatedAt": updated,
    }


def _build_command() -> list[str]:
    cmd = [
        _resolve_pi_bin(),
        "--mode", "rpc",
        "--no-builtin-tools",          # 不让模型碰文件系统 / shell
        "-e", _resolve_extension(),
    ]
    # 小瑷的角色 / 输出规范（追加，不覆盖 pi 默认提示）。可用环境变量覆盖或置空。
    system_prompt = _resolve_system_prompt()
    if system_prompt and Path(system_prompt).is_file():
        cmd += ["--append-system-prompt", system_prompt]
    model = os.environ.get("AEGIS_PI_MODEL")
    if model:
        cmd += ["--model", model]
    return cmd


class PiBridge:
    """把一个 pi RPC 子进程桥接到一个 WebSocket。"""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self.proc: Optional[subprocess.Popen[bytes]] = None

    def start(self) -> None:
        cwd = os.environ.get("AEGIS_PI_CWD") or None
        env = os.environ.copy()
        # 桥是本地组件，可代为取用当前 UI token；也默认声明本会话能力，
        # 使只读工具免于每次都弹确认。
        env["AEGIS_UI_TOKEN"] = _fetch_ui_token() or env.get("AEGIS_UI_TOKEN", "")
        env.setdefault("AEGIS_SESSION_CAPABILITIES", "unknown_tool")
        self.proc = subprocess.Popen(
            _build_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            bufsize=0,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        # Python 的 readline 只按 \n 切分（不像 Node readline 会切 U+2028/2029），符合 RPC 要求
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.rstrip(b"\r\n")
            if line:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, line.decode("utf-8", "replace"))
        self.loop.call_soon_threadsafe(self.queue.put_nowait, None)  # EOF 哨兵

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for raw in iter(self.proc.stderr.readline, b""):
            text = raw.decode("utf-8", "replace").rstrip()
            if text:
                payload = json.dumps({"type": "bridge_stderr", "text": text}, ensure_ascii=False)
                self.loop.call_soon_threadsafe(self.queue.put_nowait, payload)

    def send(self, command: dict[str, Any]) -> None:
        if not self.proc or self.proc.stdin is None:
            raise RuntimeError("pi 子进程未就绪")
        data = (json.dumps(command, ensure_ascii=False) + "\n").encode("utf-8")
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass


def _authorize(token: Optional[str]) -> bool:
    expected = os.environ.get("AEGIS_PI_TOKEN", "").strip()
    if not expected:
        return True
    return bool(token) and token == expected


@router.get("/status")
async def guide_status() -> dict[str, Any]:
    """给前端探测：pi 是否可执行、扩展路径是否存在。"""
    binary = _resolve_pi_bin()
    ext = _resolve_extension()
    return {
        "pi_binary": binary,
        "pi_available": shutil.which(binary) is not None,
        "extension": ext,
        "extension_exists": Path(ext).exists(),
        "model": os.environ.get("AEGIS_PI_MODEL"),
        "auth_required": bool(os.environ.get("AEGIS_PI_TOKEN", "").strip()),
    }


# 静态前端：聊天界面（浏览器直接打开 /api/aegis-guide/chat 即可）
_FRONTEND_FILES = {
    "aegis-chat.css": "text/css; charset=utf-8",
    "aegis-chat.js": "application/javascript; charset=utf-8",
    "aegis-guide.css": "text/css; charset=utf-8",
    "aegis-guide.js": "application/javascript; charset=utf-8",
}


@router.get("/chat", include_in_schema=False)
async def guide_chat() -> FileResponse:
    """完整版聊天界面（豆包/ChatGPT 风格）。"""
    return FileResponse(_FRONTEND_DIR / "aegis-chat.html", media_type="text/html; charset=utf-8")


@router.get("/static/{filename}", include_in_schema=False)
async def guide_static(filename: str) -> FileResponse:
    """只服务白名单内的前端资源，避免路径穿越。"""
    media = _FRONTEND_FILES.get(filename)
    if not media:
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(_FRONTEND_DIR / filename, media_type=media)


@router.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    """列出 pi 在当前项目下的所有会话（服务端会话记录，非浏览器本地）。"""
    directory = _session_dir()
    items: list[dict[str, Any]] = []
    if directory.is_dir():
        for path in directory.glob("*.jsonl"):
            try:
                info = _read_session_info(path)
            except Exception:  # noqa: BLE001 - 单个坏文件不影响列表
                continue
            if info["messageCount"] > 0:  # 跳过空会话（仅系统提示）
                items.append(info)
    items.sort(key=lambda item: item.get("updatedAt", 0), reverse=True)
    return {"conversations": items, "sessionDir": str(directory)}


@router.delete("/conversations/{name}")
async def delete_conversation(name: str) -> dict[str, Any]:
    """删除一个会话文件（仅限当前项目的会话目录内）。"""
    if (
        not name.endswith(".jsonl")
        or "/" in name
        or "\\" in name
        or ".." in name
    ):
        raise HTTPException(status_code=400, detail="invalid session name")
    directory = _session_dir().resolve()
    target = (directory / name).resolve()
    if target.parent != directory or not target.is_file():
        raise HTTPException(status_code=404, detail="session not found")
    target.unlink()
    return {"deleted": True, "name": name}


@router.websocket("/ws")
async def guide_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token") or websocket.headers.get("x-aegis-ui-token")
    if not _authorize(token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    loop = asyncio.get_running_loop()
    bridge = PiBridge(loop)

    try:
        bridge.start()
    except Exception as exc:  # noqa: BLE001 - 报告给前端，不抛 500
        await websocket.send_text(
            json.dumps({"type": "bridge_error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
        )
        await websocket.close()
        return

    async def pump() -> None:
        try:
            while True:
                line = await bridge.queue.get()
                if line is None:
                    break
                await websocket.send_text(line)
        except Exception:
            pass

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                command = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "bridge_error", "error": "invalid JSON"}, ensure_ascii=False)
                )
                continue
            try:
                bridge.send(command)
            except Exception as exc:  # noqa: BLE001
                await websocket.send_text(
                    json.dumps({"type": "bridge_error", "error": str(exc)}, ensure_ascii=False)
                )
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        bridge.stop()
