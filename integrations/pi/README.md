# Aegis × pi 集成（上层层）

让 **pi** 扮演 Aegis 平台的「对话式向导 + 报表助手」，并把 pi 自身变成一个**被 Aegis 治理的 `runtime_kind`**。

> **不改动 Aegis 现有代码。** `SecurityAnalystAgent`（LangGraph）、`/api/security-operations/*`、`/api/runtime/*` 全部原样复用。

## 架构

```
用户 ⇄ pi（对话 / 向导 / 表格）
           │  自定义工具 = fetch()
           ▼
  Aegis FastAPI (127.0.0.1:8741)
   ├── /api/security-operations/*   ← Agent / 证据 / RAG / 记忆
   └── /api/runtime/*               ← 五阶段裁决 / 事件审计 / 免疫 / 能力清单
           ▼
  SecurityAnalystAgent (LangGraph，不动)
```

## 三层能力

| 层 | 机制 | 文件 |
|---|---|---|
| 只读工具 | 16 个 `aegis_*` 工具，直连 GET/POST 只读端点 | `aegis-guide.ts` |
| 有副作用工具 | 7 个 `aegis_*` 工具，UI token + 交互确认 | `aegis-guide.ts` |
| 治理钩子 | pi 的 `input` / `tool_call` / `tool_result` → Aegis 运行时 | `aegis-guide.ts` |
| 向导 | 按需加载的领域技能 | `skills/aegis-guide/SKILL.md` |

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `AEGIS_BASE_URL` | `http://127.0.0.1:8741` | Aegis 应用地址 |
| `AEGIS_API_PREFIX` | `/api` | 应用级挂载前缀（`app.py` 里 `include_router(..., prefix="/api")`） |
| `AEGIS_SESSION_CAPABILITIES` | 空 | 本会话声明的能力，透传给 `decide` 的 `allowed_capabilities`；例 `file_read,unknown_tool` |
| `AEGIS_UI_TOKEN` | 空 | 写操作必需（对应 `X-Aegis-UI-Token`） |
| `AEGIS_APPROVER` | `pi-operator` | 审批人标识，**绝不来自模型** |
| `AEGIS_RUNTIME_KIND` | `pi` | 在 Aegis 审计中标识 pi |
| `AEGIS_PI_FAIL_MODE` | `open` | Aegis 不可达时：`open` 放行 / `closed` 拦截 |
| `AEGIS_INGRESS_TOKEN` | 空 | 若 Aegis 设了 ingress token，则所有请求自动带 `X-Api-Key` |

## 运行

```bash
# 1) 先起 Aegis
aegis-app --web                      # → http://127.0.0.1:8741

# 2) 起 pi（禁用内置工具，避免模型碰文件系统）
export AEGIS_BASE_URL=http://127.0.0.1:8741
export AEGIS_UI_TOKEN=<你的 UI token>
export AEGIS_APPROVER=<操作人标识>
# 让只读 aegis_* 工具免于每次人工确认（否则会被判为未声明的 unknown_tool）
export AEGIS_SESSION_CAPABILITIES=unknown_tool
pi --no-builtin-tools -e ./integrations/pi/aegis-guide.ts --model deepseek/deepseek-chat
```

在 pi 里用 `/aegis` 查看连接状态；改完扩展用 `/reload` 热加载。

## 治理钩子做了什么

| pi 事件 | 调用 | 效果 |
|---|---|---|
| `input` | `POST /api/runtime/intent` | 把用户每一轮的输入作为意图基线交给 Aegis |
| `tool_call` | `POST /api/runtime/pretool/decide` | 跑五阶段裁决；`decide` 内部会落 `before_tool_call` 事件 |
| `tool_result` | `POST /api/runtime/events`（`after_tool_call`） | 落执行结果元数据（只记 `tool_name` / `is_error`，不记内容） |

裁决结果 `action` 的处置：

- `block` → 直接阻断该工具调用
- `confirm` → 弹窗确认（`SELF_GATED` 中的工具自己做更强确认，不重复弹）
- `allow` → 放行

## 工具清单

**只读（16）**
`aegis_search_knowledge` · `aegis_list_evidence` · `aegis_list_runs` · `aegis_inspect_run` ·
`aegis_export_run`* · `aegis_tool_catalog` · `aegis_model_status` · `aegis_list_memories` ·
`aegis_benchmarks` · `aegis_runtime_config` · `aegis_list_sessions` · `aegis_get_session` ·
`aegis_list_antibodies` · `aegis_list_immune_matches` · `aegis_list_manifests` · `aegis_evaluation_dataset`

（\* `aegis_export_run` 语义只读，但 Aegis 端点要求 UI token。）

**有副作用（7，均带交互确认）**
`aegis_submit_run` · `aegis_resume_run` · `aegis_cancel_run` · `aegis_run_evaluation` ·
`aegis_grant_trust` · `aegis_transition_antibody` · `aegis_create_memory`

（除 `aegis_run_evaluation` 外均需 UI token；`/api/runtime/evaluations` 端点本身不校验 token。）

**明确不暴露**：`POST /evidence/upload`、`/model-credentials/*`（密钥）——这些留给人工在 Web UI 操作。

## 四条红线

1. **禁用内置工具**：`--no-builtin-tools`，pi 不接触文件系统 / shell。
2. **`approved_by` 绝不来自模型**：从 `AEGIS_APPROVER` 读。
3. **审批必须弹窗**：`aegis_resume_run` 展示完整 `proposal_hash` 才发送。
4. **UI token 只从 env 读**，不进模型上下文。

## 性能与姿态

- `decide` 是**无 LLM 热路径**（五阶段确定性）。每轮对话新增：1 次 `intent` + 每次工具 1 次 `decide` + 1 次 `after_tool_call`。
- 失败姿态默认 **fail-open**，与 Aegis 的 Claude Code 插件一致；要 fail-closed 就设 `AEGIS_PI_FAIL_MODE=closed`。

## 嵌进 Web 产品（本目录已含完整实现）

Aegis 是 Python/FastAPI，因此走 **pi RPC 子进程 + WebSocket 桥**：

```
浏览器  ⇄  /api/aegis-guide/ws  ⇄  FastAPI 桥  ⇄  pi --mode rpc 子进程
  聊天UI + 表格渲染 + 审批弹窗            (backend/aegis_guide_ws.py)      (aegis-guide.ts)
```

桥是**极薄双向管道**：浏览器直接说 pi RPC 协议，无需自定义协议。

### 文件

| 文件 | 作用 |
|---|---|
| `backend/aegis_guide_ws.py` | FastAPI 路由：`/api/aegis-guide/ws`（WS）与 `/api/aegis-guide/status` |
| `frontend/aegis-guide.js` | 纯 JS 客户端：流式文本、`details.table` 渲染、审批弹窗 |
| `frontend/aegis-guide.css` | 样式 |
| `frontend/example.html` | 最小宿主页，改路径即可用 |

### 挂载（在你现有 `app.py` 加一行）

```python
from integrations.pi.backend.aegis_guide_ws import router as aegis_guide_router
app.include_router(aegis_guide_router)
```

桥的环境变量见 `backend/aegis_guide_ws.py` 顶部（`AEGIS_PI_BIN` / `AEGIS_PI_EXTENSION` / `AEGIS_PI_MODEL` / `AEGIS_PI_TOKEN` 等）。

### 数据流（关键映射）

| 前端动作 | 发给 pi | 后端返回 | 前端渲染 |
|---|---|---|---|
| 发消息 | `{"type":"prompt","message":...}` | `message_update`（`text_delta`） | 流式文本 |
| —— | —— | `tool_execution_end.result.details.table` | **HTML 表格** |
| —— | —— | `extension_ui_request`（`confirm`/`select`/`input`） | 审批弹窗 → 回 `extension_ui_response` |
| —— | —— | `extension_ui_request`（`notify`） | 通知条 |

> 扩展里的 `aegis_resume_run` / `aegis_grant_trust` 的 `ctx.ui.confirm`，在 RPC 模式下会自动变成 `extension_ui_request`，**由浏览器弹窗并回传结果**——这正是把「人工审批」搬进 Web UI 的机制。

### 独立调试

不想动 Aegis 主应用时，桥也可单独跑（它只依赖 FastAPI）：

```python
# dev_bridge.py
from fastapi import FastAPI
from integrations.pi.backend.aegis_guide_ws import router
app = FastAPI(); app.include_router(router)
# uvicorn dev_bridge:app --port 8790
```

### 注意
- 若你的 Web 前端有构建流程，`aegis-guide.js` 可直接引入或包成组件。
- Windows 下用 `subprocess.Popen` + 线程桥接（本实现即如此），不依赖 asyncio 子进程，避开 Windows 事件循环限制。

## 冒烟测试

`smoke_test.py` 分两段验证（不依赖 Aegis 主应用改动）：

```bash
export AEGIS_BASE_URL=http://127.0.0.1:8741
export AEGIS_PI_MODEL=deepseek/deepseek-chat
python integrations/pi/smoke_test.py

# 只跑不依赖模型的第一段
AEGIS_SMOKE_SKIP_LLM=1 python integrations/pi/smoke_test.py
```

| 阶段 | 验证内容 | 是否需模型 |
|---|---|---|
| Phase 1 | 直接 `POST /api/runtime/pretool/decide` → 断言返回 `action` + 事件链落 `before_tool_call` | 否（确定性） |
| Phase 2 | 起 `pi --mode rpc` → 断言 `tool_execution_end.result.details.table` + 该工具的 `before_tool_call` 审计 | 是 |

退出码：`0` 通过 / `1` 失败 / `2` 环境未就绪。

> Phase 2 遇到 `extension_ui_request` 会自动回**批准**（模拟配合的操作员），以便验证「表格渲染 + 审计落库」正向链路；Phase 2 还会自动设置 `AEGIS_SESSION_CAPABILITIES=unknown_tool`（除非已被覆盖），避免只读工具被确认框卡住。
>
> Windows 上 `pi` 由 npm 安装为 `pi.CMD`，Python 的 `subprocess` 对裸 `pi` 只会尝试 `.exe`；测试与 Web 桥均已用 `shutil.which("pi")` 解析真实路径。

## 验证状态（本轮实测）

在 Aegis `1.0.1`（仓库源码）+ pi `0.87.0` 上实测：

| 检查 | 命令 / 方式 | 结果 |
|---|---|---|
| 扩展类型 | `tsc --noEmit`（对照 pi 0.87.0 类型声明） | ✅ 0 error |
| Python 语法 | `py_compile`（`smoke_test.py`、`backend/aegis_guide_ws.py`） | ✅ |
| 契约路径 | 对照 `/openapi.json` 与 `app.py` 的 `include_router(prefix="/api")` | ✅ 已修正 `/api` 前缀 |
| 冒烟 Phase 1 | `AEGIS_SMOKE_SKIP_LLM=1 python integrations/pi/smoke_test.py` | ✅ PASS（exit 0） |
| 冒烟 Phase 2 | `AEGIS_PI_MODEL=deepseek/deepseek-flash python integrations/pi/smoke_test.py` | ✅ PASS（exit 0） |
| Web 桥 | Starlette `TestClient` 走 `/api/aegis-guide/ws` 全链路 | ✅ 表格事件 + 审计落库 |

> 注：`aegis_tool_catalog`（`/api/security-operations/agent/tools`）与 `aegis_model_status`（`/agent/model`）依赖 `langgraph`，在未安装 Agent 依赖的环境返回 503，属预期。
