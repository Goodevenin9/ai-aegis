#!/usr/bin/env python3
"""Aegis × pi 端到端 smoke test。

分两段，降低模型不稳定导致的假阴性：

  Phase 1（不需要模型，确定性）
    直接 POST /runtime/pretool/decide，断言：
      - 返回含 action（allow/confirm/block）
      - 该会话的事件链里出现 before_tool_call（审计落库）

  Phase 2（需要模型）
    启动 `pi --mode rpc`，发一句强制调用 aegis_search_knowledge 的提示，断言：
      - 收到 tool_execution_end.result.details.table （前端表格数据）
      - 会话事件链里出现 tool_name=aegis_search_knowledge 的 before_tool_call

用法：
    export AEGIS_BASE_URL=http://127.0.0.1:8741
    export AEGIS_PI_MODEL=deepseek/deepseek-chat
    python integrations/pi/smoke_test.py

    AEGIS_SMOKE_SKIP_LLM=1    只跑 Phase 1
    AEGIS_SMOKE_TIMEOUT=120   Phase 2 超时秒数

退出码：0 通过 / 1 失败 / 2 环境未就绪
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# Windows 控制台默认 GBK，打印 ✓/✗/→ 会抛 UnicodeEncodeError；强制 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

BASE = os.environ.get("AEGIS_BASE_URL", "http://127.0.0.1:8741").rstrip("/")
# Aegis 应用级挂载前缀（app.py 里 include_router(..., prefix="/api")）
API = os.environ.get("AEGIS_API_PREFIX", "/api").rstrip("/")
PI_BIN = os.environ.get("AEGIS_PI_BIN") or shutil.which("pi") or "pi"
EXT = os.environ.get("AEGIS_PI_EXTENSION", str(Path(__file__).resolve().parent / "aegis-guide.ts"))
MODEL = os.environ.get("AEGIS_PI_MODEL")
RUNTIME_KIND = os.environ.get("AEGIS_RUNTIME_KIND", "pi")
INGRESS = os.environ.get("AEGIS_INGRESS_TOKEN", "").strip()
SKIP_LLM = os.environ.get("AEGIS_SMOKE_SKIP_LLM") == "1"
TIMEOUT = float(os.environ.get("AEGIS_SMOKE_TIMEOUT", "120"))

_HEADERS = {"Content-Type": "application/json"}
if INGRESS:
    _HEADERS["X-Api-Key"] = INGRESS

GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{RST}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{RST}")


def info(msg: str) -> None:
    print(f"{DIM}    {msg}{RST}")


def http(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}


# ---------------------------------------------------------------------------
# Phase 1 —— 无需模型的裁决 + 审计
# ---------------------------------------------------------------------------
def phase1() -> bool:
    print("\n[Phase 1] 五阶段裁决 + 审计落库（无需模型）")
    session_id = f"smoke-{uuid.uuid4().hex[:12]}"

    status, decision = http(
        "POST",
        f"{API}/runtime/pretool/decide",
        {
            "tool_name": "aegis_search_knowledge",
            "tool_input": {"query": "访问控制", "limit": 3},
            "session_id": session_id,
            "runtime_kind": RUNTIME_KIND,
            "base_decision": "allow",
            "manifest_id": "default",
        },
    )
    if status != 200:
        fail(f"POST /runtime/pretool/decide → {status} {decision}")
        return False
    action = decision.get("action")
    if action not in {"allow", "confirm", "block"}:
        fail(f"decide 返回缺少合法 action：{decision}")
        return False
    ok(f"decide 返回 action={action} risk={decision.get('risk_score')} drift={decision.get('drift_score')}")
    info(f"reason: {decision.get('reason')}")

    status, sess = http("GET", f"{API}/runtime/sessions/{session_id}?runtime_kind={RUNTIME_KIND}&limit=200")
    if status != 200:
        fail(f"GET /runtime/sessions/{session_id} → {status} {sess}")
        return False
    events = sess.get("events", [])
    before = [e for e in events if e.get("event_type") == "before_tool_call"]
    if not before:
        fail("会话链里没有 before_tool_call 事件（审计未落库）")
        info(f"实际事件类型：{[e.get('event_type') for e in events]}")
        return False
    ok(f"审计已落库：before_tool_call × {len(before)}，链完整性 valid={sess.get('integrity', {}).get('valid')}")
    return True


# ---------------------------------------------------------------------------
# Phase 2 —— 真实 pi RPC
# ---------------------------------------------------------------------------
class PiRPC:
    def __init__(self) -> None:
        cmd = [PI_BIN, "--mode", "rpc", "--no-builtin-tools", "-e", EXT]
        if MODEL:
            cmd += ["--model", MODEL]
        info(f"$ {' '.join(cmd)}")
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.q: "queue.Queue[dict | None]" = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.proc.stdout
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.rstrip(b"\r\n")
            if not line:
                continue
            try:
                self.q.put(json.loads(line.decode("utf-8", "replace")))
            except json.JSONDecodeError:
                self.q.put({"type": "unparsed", "raw": line.decode("utf-8", "replace")})
        self.q.put(None)

    def send(self, obj: dict) -> None:
        assert self.proc.stdin
        self.proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def wait_response(self, command: str, timeout: float = 30.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ev = self.q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                return None
            if ev and ev.get("type") == "response" and ev.get("command") == command:
                return ev
        return None

    def stop(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()


def phase2() -> bool:
    print("\n[Phase 2] 真实 pi RPC：工具表格 + 治理钩子（需要模型）")

    # 声明本次 pi 会话的能力，使 decide 不把 aegis_* 工具当作未声明的 unknown_tool。
    # （与 Aegis Claude Code 插件的 AEGIS_SESSION_CAPABILITIES 同义；可用同名单环境变量覆盖）
    os.environ.setdefault("AEGIS_SESSION_CAPABILITIES", "unknown_tool")

    pi = PiRPC()
    try:
        # 会话 id（扩展用它作为 runtime_kind=pi 的 session_id）
        pi.send({"type": "get_session_stats"})
        stats = pi.wait_response("get_session_stats", timeout=30)
        if not stats:
            fail("未收到 get_session_stats 响应（pi 可能启动失败）")
            if pi.proc.stderr:
                err = pi.proc.stderr.read(4000).decode("utf-8", "replace").strip()
                if err:
                    info(f"pi stderr: {err[:800]}")
            return False
        session_id = (stats.get("data") or {}).get("sessionId")
        ok(f"pi 会话已建立 sessionId={session_id}")

        # 发一句强制调用 aegis_search_knowledge
        pi.send(
            {
                "type": "prompt",
                "message": (
                    "必须调用工具 aegis_search_knowledge，参数 query='访问控制'，limit=3，"
                    "然后把工具返回的表格原样展示出来。不要调用其它工具。"
                ),
            }
        )
        ok("已发送 prompt")

        table_seen = False
        settle_seen = False
        tool_error = None
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            try:
                ev = pi.q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if ev is None:
                fail("pi 进程提前退出")
                return False
            t = ev.get("type")
            if t == "tool_execution_end" and ev.get("toolName") == "aegis_search_knowledge":
                details = (ev.get("result") or {}).get("details") or {}
                if isinstance(details.get("table"), dict):
                    table_seen = True
                    rows = len(details["table"].get("rows") or [])
                    ok(f"收到工具表格 details.table（{rows} 行）")
                elif ev.get("isError"):
                    tool_error = (ev.get("result") or {}).get("content")
            elif t == "extension_ui_request" and ev.get("method") != "notify":
                # 本测试验证的是「表格渲染 + 审计落库」正向链路，因此模拟一个
                # 配合的操作员：自动批准确认框（而非拒绝），避免卡在审批上。
                info(f"自动批准 extension_ui_request: {ev.get('method')}")
                pi.send({"type": "extension_ui_response", "id": ev.get("id"), "confirmed": True})
            elif t == "agent_settled":
                settle_seen = True
                break
            elif t in ("bridge_error", "extension_error"):
                fail(f"{t}: {ev.get('error') or ev.get('message')}")

        if not settle_seen:
            info("未观察到 agent_settled（可能超时），继续校验审计链")

        # 校验治理钩子是否把该工具调用落库
        audit_ok = False
        if session_id:
            status, sess = http(
                "GET", f"{API}/runtime/sessions/{session_id}?runtime_kind={RUNTIME_KIND}&limit=500"
            )
            if status == 200:
                hits = [
                    e
                    for e in sess.get("events", [])
                    if e.get("event_type") == "before_tool_call"
                    and (e.get("payload") or {}).get("tool_name") == "aegis_search_knowledge"
                ]
                audit_ok = bool(hits)
                if audit_ok:
                    ok(f"治理钩子已落库 {len(hits)} 条 aegis_search_knowledge 的 before_tool_call")
                else:
                    fail("未找到该工具的 before_tool_call 审计事件")
            else:
                fail(f"GET /runtime/sessions/{session_id} → {status}")

        if tool_error:
            fail(f"工具返回错误：{tool_error}")

        return table_seen and audit_ok
    finally:
        pi.stop()


# ---------------------------------------------------------------------------
def main() -> int:
    print(f"Aegis × pi smoke test  →  {BASE}")

    status, health = http("GET", "/health")
    if status == 0:
        fail(f"Aegis 不可达：{health.get('error')}")
        print("请先运行：aegis-app --web")
        return 2
    ok(f"Aegis 在线 (HTTP {status}, status={health.get('status')})")

    results = [("Phase 1 裁决+审计", phase1())]
    if SKIP_LLM:
        print(f"\n{YEL}跳过 Phase 2（AEGIS_SMOKE_SKIP_LLM=1）{RST}")
    else:
        results.append(("Phase 2 pi+e2e", phase2()))

    print("\n===== 结果 =====")
    failed = False
    for name, passed in results:
        print(f"  {GREEN}PASS{RST}  {name}" if passed else f"  {RED}FAIL{RST}  {name}")
        failed = failed or not passed
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
