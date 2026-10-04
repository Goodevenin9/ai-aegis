# Changelog

本项目包含基于 Apache License 2.0 上游项目演进的代码，完整来源与版权归属见
[NOTICE](NOTICE) 与 [LICENSE](LICENSE)。

## 1.0.3 — 未发布

**前后端能力对齐 + 版本自证一致**

### 修复
- **版本号统一**：`aegis.app.__version__`、两个 CLI、控制平面与 MCP 服务器改为从 `aegis.__version__` 单一来源派生。此前 `/health`、CLI 与包元数据各自自报 1.0.0 / 1.0.1 / 1.0.2，测试者会以为自己装错版本
- **未知 `/api/*` 返回 JSON 404**：SPA catch-all 之前会把任何 GET 都返回 200 + HTML 外壳，导致 API 消费者解析 HTML、并在 live 集成测试里表现为 `JSONDecodeError`
- **小瑷 导航项按能力显示**：小瑷 依赖可选的 `pi` 集成（仅源码仓库挂载 + 本机需有 `pi` CLI）。安装版此前会显示入口但 iframe 指向 404；现在侧栏与页面都先探测 `/api/aegis-guide/status`，不可用时整个入口隐藏并给出空状态。`integrations/` 仍不进 wheel（有意保持源码专用）
- **README 与产品数字对齐**：72 → 108 条规则（四处）、头部版本 1.0.3、移除指向空 releases 页的 5 个二进制下载按钮（并说明 `.exe/.deb/.rpm/.dmg` 尚未发布）
- **`[mcp]` 依赖修正**：`aegis.mcp.auth_validator` 直接 `import httpx`，但 `[mcp]` 未声明它；而 `mcp`/`fastmcp` 的无上限 `>=` 会装到 mcp 2.x / fastmcp 4.x（改用 httpx2、导入面已变）。已声明 `httpx` 并把两个依赖封顶到 `<2` / `<3`。发布 workflow 的可选 MCP 校验改为警告，不再因可选 extra 阻塞基础包发布

### 新增
- 补齐两个缺失的工具调用频率限制端点：`PUT /api/tool-permissions/overrides/{tool_id}/rate-limit` 与 `PUT /api/tool-permissions/custom/{tool_id}/rate-limit`（前端 `api.js` 一直调用它们，但路由从未存在；数据库列与仓库方法早已就绪）
- 安全运营页补上后端已有但前端未展示的四项能力：RAG 评测（Recall@k / MRR）、Agent 工具目录、外部基准结果、删除受治理记忆
- 会话安全页新增「Immunity matches」面板（`GET /api/runtime/immunity/matches`）
- 设置页新增「Device Identity」区块，可重置本机 device ID（克隆 VM 恢复）
- Agent Egress 页新增「Audit」标签页；Tool Permissions 页新增「Local overrides & rate limits」面板，可读可改每个工具的调用频率上限

### 测试与 CI
- 新增 `tests/unit/app/test_release_contracts.py`：版本单一来源一致性、未知 `/api/*` 必须 404 JSON、SPA 页面路由仍返回 HTML
- 新增 `scripts/run_live_integration.py`：启动 app（+可选 proxy）、等健康、跑 `-m integration`、必清理，供本地与 CI 复现 live 测试
- 新增 CI 门禁 `integration-plugin-e2e`（插件 → hook → API → 审计，自包含，14 条，此前被 `-m "not integration"` 永久排除）；app+proxy 依赖的 live 测试暂以 manual + 非阻塞 workflow 保留

### 清理
- 删除 `api.js` 中四个从未被调用的死包装（`getThreat` / `deleteThreat` / `getSiemForwarder` / `testSecurityAgentModel`），并把 `integrations.js`、`threats.js` 的裸 `fetch` 改为走 API 客户端
- 品牌完整性测试为竞品对比文档加白名单（文档点名竞争对手是其目的）
- `.gitignore` 忽略仓库根 `tmp/` 临时目录

## 1.0.2 — 2026-09-10

**模型凭据可在网页配置**

### 新增
- 安全运营页新增“模型凭据”卡片：直接输入 DeepSeek API 密钥，保存后**即时生效**，无需重启。保存成功后自动执行一次双路连接测试（Agent 模型 + Drift 语义提取），分别显示两条链路各自的连通状态
- 同卡片提供 `AEGIS_DRIFT_LLM_ENABLED` 漂移提取开关及其状态徽标，消除“以为开着其实没开”的静默失败
- 新增 `PUT` / `DELETE` / `POST .../test` 三个凭据端点与只读的 `GET /api/security-operations/model-credentials`

### 安全
- 密钥本体与密钥文件路径**永不返回网页**，只返回末四位掩码（如 `sk-****3f7a`）；密钥不写日志、不进异常消息
- 密钥存于用户数据目录下的 `model_key` 文件（0600 权限、单次 `open()` 原子写），不进 SQLite，不会随备份或证据导出外泄
- 三个写入类端点均要求 UI 令牌，缺失返回 403；由 `--key-file` 启动参数提供的密钥文件属启动侧所有，网页删除会返回 409 而非静默删除
- 网页写入后会提升该文件优先级，避免本机一个失效的旧 `DEEPSEEK_API_KEY` 静默覆盖新密钥

### 已知问题
- PyPI 的 `license_expression` 仍为 `None`。1.0.1 的 CHANGELOG 声称已改为 PEP 639 的 SPDX 表达式，经核对该版本实际上并未生效，此处更正。改用 `[project]` 表声明 license 是独立改动，未包含在本版本内；当前元数据为 `License: Apache-2.0` + `License :: OSI Approved :: Apache Software License` classifier

## 1.0.1 — 2026-09-10

**品牌标识与文档修正**

> 1.0.0 打包的是旧图标，而 PyPI 同一版本的内容不可修改，因此需要发此版本。

### 修复
- 产品内全部图标替换为 AI Aegis 盾牌标识：应用 Web UI（侧栏 / 顶部导航 / 浏览器标签页）、安装器图标、Cursor 插件、PDF 导出中内嵌的 base64 图标
- ~~PyPI 元数据补上 `license_expression`，改为 PEP 639 的 SPDX 表达式写入~~ —— **此条不成立，1.0.2 时更正**。当时以为已生效，实际 PyPI 上 1.0.1 的 `license_expression` 仍为 `None`：setup.py-only 的构建拿不到 PEP 639 待遇（需要 `[project]` 表），元数据里落的是传统的 `License: Apache-2.0` 加 classifier。见 1.0.2 的「已知问题」
- 移除文档中并不存在的二进制安装包下载（`.exe` / `.dmg` / `.deb` / `.rpm` / `.AppImage`）——pip 与源码安装是唯一可用路径
- 修正 `docs/MCP_GUIDE.md`：包名 `aegis[mcp]` → `ai-aegis[mcp]`（`aegis` 是 PyPI 上他人的包）、仓库目录名，以及无法拉取的预构建镜像说明（改为从 `Dockerfile.mcp` 本地构建）
- 贡献指南依赖命令 `.[dev]` → `.[dev,app]`（`.[dev]` 缺少 `aiosqlite` / `sqlalchemy`，会导致测试收集失败）

## 1.0.0 — 2026-08-31

**初始发布：AI Aegis（灵盾）**

### 新增（本团队二次开发增量）
- 前端中英文切换（i18n）：运行时 DOM 翻译引擎 + 中文字典，英文界面与原版逐字节一致
- 品牌重塑：AI Aegis（灵盾），包名 `ai-aegis`，CLI `aegis` / `aegis-monitor` / `aegis-mcp` / `aegis-app` / `aegis-proxy`

### 保留（上游功能，全量迁移）
- 72 条规则 + Guardian ML 检测层（`bundled AI Aegis Guardian`，Apache-2.0）
- 本地 / API / 混合三种检测模式
- 桌面应用（FastAPI + Web 前端）：威胁/规则/工具权限/成本/Agent 地图等全部页面
- Claude Code / Codex / Copilot CLI / Cursor / OpenClaw 插件 hook
- MCP 服务、SIEM 导出、实时监控与事件回放
