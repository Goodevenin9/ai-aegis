# Aegis 使用向导（pi Skill）

当用户询问「Aegis 怎么用 / 如何接入某个 Agent / 在哪里看审计与成本 / 怎么配权限」时使用本技能。

## 回答原则

1. 先给**一句话结论**，再给分步操作。
2. 涉及端点、端口、文件路径时，用**表格**呈现（表格数据来自 `aegis_*` 工具，不要手编）。
3. 拿不到证据就说「需要核验」，**不要编造**端点、规则编号或数字。
4. 高风险动作（提交分析 `aegis_submit_run`、审批策略 `aegis_resume_run`、JIT 授权 `aegis_grant_trust`）**必须先向用户确认**。

## 平台能力地图

| 需求 | 入口 | 说明 |
|---|---|---|
| 接入某个 Agent | Integrations 页 | 装原生插件（Claude Code / Codex / Copilot CLI / Cursor / OpenClaw）或起 LLM Proxy（端口 8742） |
| 看工具调用审计 | Dashboard → Traces | 逐次工具调用的 allow/block 裁决、风险、原因；SHA-256 哈希链可验 |
| 看 Agent 全局 | Agent Map | device → harness → agent → tool，tree/radial/mesh/Sankey 视图 |
| 管工具权限 | Tool Permissions | allow / deny / ask；JIT 授权（15 分钟 / 1 小时 / 单会话，自动过期） |
| 看成本 | Cost Tracker | 按 agent / model 的 token 与 USD；每日预算自动停止 |
| 装前扫描 | Skill Scanner | 安装前静态审计 skill/工具包（10 类：shell、网络、env、code exec…） |
| 威胁检测 | 自动运行 | 72 条规则 + Guardian ML（本地离线）；OWASP LLM Top 10 + 28 条 agent 攻击链 |
| 导出与转发 | 审计 PDF / SIEM Forwarder | OCSF 1.3.0 → Splunk / Datadog / Sentinel / Chronicle / QRadar / OTLP / webhook / NDJSON（默认仅元数据） |
| 平台内分析 | Security Operations | 证据 / RAG / 记忆 + 有界安全分析 Agent（本向导的核心工具来源） |

## 安全分析 Agent 的工作方式（解释用）

- 任务类型：`general_explanation` / `knowledge_query` / `incident_investigation` / `evidence_analysis` / `dataset_evaluation` / `policy_change`
- 它是**有界**的：只读工具、无命令执行、策略变更必须**人工审批**后由确定性代码应用
- 查看运行：`aegis_list_runs` → `aegis_inspect_run`；导出：`aegis_export_run`

## 端口与路径速查

| 项 | 值 |
|---|---|
| 应用 / API | `127.0.0.1:8741` |
| LLM Proxy | `127.0.0.1:8742`（默认 = server.port + 1） |
| 配置 | `aegis.yml`（应用数据目录，启动时打印路径） |
| 接入 OpenAI 兼容 | `OPENAI_BASE_URL=http://localhost:8742/openai/v1` |
| 接入 Anthropic | `ANTHROPIC_BASE_URL=http://localhost:8742/anthropic` |

## 不要做的事

- 不要声称能修改策略（`PUT /api/runtime/config` 已禁用，返回 409）。
- 不要向模型索取或输出任何 API key / UI token。
- 不要在没有用户确认的情况下执行 `aegis_submit_run` / `aegis_resume_run` / `aegis_grant_trust`。
