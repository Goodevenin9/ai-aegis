# 五段式 PreToolUse 会话安全管线

AI Aegis 在既有工具权限、出站策略和哈希链审计之上增加独立的会话层：

```text
UserPromptSubmit ──异步──> DeepSeek 语义标签 ──> Session Drift Store + SQLite
                                                       │
AI Aegis single-turn verdict ──> Boundary → Capability → Radius → Drift → Friction
                                                                  │
                                                        allow / confirm / block
```

设计原则是“LLM 提取证据，代码负责裁决”。`PreToolUse` 热路径不会调用大模型；同一输入的权重、状态转移和最终结果均可复现。

## 分层职责

| 层 | 原型实现 | LLM 参与 | 是否可单独阻断 |
| --- | --- | --- | --- |
| Boundary | NFKC/零宽字符归一化、中文越狱、高危 Shell、敏感路径规则 | 否 | Critical 可直接 block |
| Capability | 结构化工具名映射后，与会话能力清单做集合匹配 | 否 | 缺失能力产生 confirm |
| Radius | 解析结构化路径、URL 和远程 MCP，分类 project/local/user/system/external | 否 | 否，仅输出证据 |
| Drift | 固定权重状态机，累积语义标签与同类风险重试 | DeepSeek 只输出 3 个 bool | 分数达到阈值可 confirm/block |
| Friction | 合并单轮基线判定和四层信号的确定性决策表 | 否；解释也由模板生成 | 唯一最终裁决点 |

P0 DeepSeek 的 Drift 输出契约为：

```json
{
  "theme_shifted": false,
  "permission_probing": false,
  "request_escalation": false
}
```

模型不能返回漂移分数、阈值或 allow/block。非布尔输出、超时、网络错误均不会进入状态机。

P1 将同一次模型调用扩展为五字段封闭证据契约：前三项仍是 Drift 布尔标签，另外两项只能是能力枚举集合和影响半径枚举。它们分别进入 Capability 与 Radius，仍不携带分数或裁决：

```json
{
  "theme_shifted": false,
  "permission_probing": false,
  "request_escalation": false,
  "requested_capabilities": ["file_read"],
  "requested_radius": "project"
}
```

允许的能力为 `file_read / file_write / shell_exec / network_outbound / unknown_tool`，半径为 `none / project / local / user / system / external`。多出字段、未知枚举、字符串形式的布尔值都会整包拒绝。

## 原型配置

- `AEGIS_SESSION_CAPABILITIES=file_read,file_write,shell_exec,network_outbound`：当前会话声明的能力清单。未配置时采用只读默认值 `file_read`；写入、Shell 和外网能力需要确认。
- `AEGIS_DRIFT_LLM_ENABLED=true`：开启 DeepSeek 语义证据提取；默认关闭。
- `AEGIS_DEEPSEEK_API_KEY`（或 `DEEPSEEK_API_KEY`）：DeepSeek API 密钥。
- `AEGIS_DEEPSEEK_API_URL`：默认 `https://api.deepseek.com/chat/completions`。
- `AEGIS_DEEPSEEK_MODEL`：默认 `deepseek-chat`。
- `AEGIS_HEADLESS=true`：无人值守模式，将 `confirm` 自动升级为 `block`；常见 CI 真值也由 Claude hook 识别。

默认漂移阈值为 40（confirm）和 80（block）。主题偏移、权限试探、请求升级分别固定增加 40、25、30；相同风险操作第二次/第三次重试额外增加 15/30。所有值集中在 `PipelineConfig`，便于离线评测和 A/B 调参。

## 审计与边界

`block`、`confirm` 以及带风险信号的 `allow` 会写入现有 `tool_call_audit` 哈希链。`reason` 保存版本化紧凑 JSON，包括各层结果、signal code、Friction 风险分、Drift 累积分和最终动作；`risk` 字段继续使用既有 `read/write/delete/admin` 枚举，避免破坏前端和历史统计。原始单轮拒绝原因会保留在摘要中。

P0 已将会话状态写入 `runtime_session_states`，并把 `before_prompt_build → llm_input → llm_output → before_tool_call → after_tool_call` 规范化为独立的 SHA-256 哈希链事件。服务重启优先恢复状态表；状态缺失时，只从完整性验证通过的事件链中恢复最近状态快照。缺少 session id 的事件只运行无状态层，避免不同匿名会话互相污染。

Claude Code、Codex、GitHub Copilot CLI、Cursor 的原生 Hook 已接入 PreToolUse 五段裁决和前后工具事件；HTTP LLM Proxy 负责捕获真实的模型输入/输出，并对响应中的结构化工具调用执行同一五段管线。所有适配均保留原有规则优先级，五段管线只能升级、不能放宽原判定。

Web 应用新增 **Session Security** 页面，按运行时/会话展示原始意图、当前 Drift 分数、五层职责、风险曲线、完整因果时间线和哈希链校验结果。

## P1 策略面与评测

P1 在保持 P0 热路径和 AI Aegis 单轮基线优先级不变的前提下增加：

- 持久化 Capability Manifest：按 `runtime_kind + manifest_id + session_id` 保存能力清单与项目根目录；精确会话 Manifest 优先，其次为运行时通配 Manifest、默认运行时的会话/通配 Manifest。Manifest 一旦存在即是权威基线，插件自报能力不能绕过；不存在时才回退到会话基线和只读安全默认值。
- 持久化 `PipelineConfig`：所有 Drift 权重和 Friction 阈值可从 Session Security 页面调整，后端校验 `confirm < block <= max_drift_score`。
- 短期信任复用：只能由持有本次本地 Web UI 令牌的人工操作授予；只复用并消耗当前工具实际需要的单项能力，同时受 TTL（最长一小时）和使用次数（最多 100 次）约束，并写入会话哈希链。
- 中文 Boundary 规则包：覆盖指令覆盖、安全绕过、隐蔽操作、无限制角色、提权、凭据访问、审计擦除、混淆逃逸、分步攻击和数据外传；明确的防御性讨论通过负向语境抑制。
- 自建 51 条中文 Agent 数据集和三组离线对照：AI Aegis 单轮判定、数据集记录的 DeepSeek-Judge 判定、五段管线。记录版 Judge 不会在离线重放时调用外部 API。
- Session Security 操作面：编辑配置和默认 Manifest、运行 A/B 评测、导出包含状态、时间线和哈希校验结果的会话证据 JSON。

默认数据集当前基准：原始判定攻击召回率 58.33%，记录版 Judge 83.33%，五段管线 91.67%。这些数值只证明该固定原型数据集上的相对效果，不代表真实生产环境效果；应继续使用独立盲测集验证。

P1 仍不实现微沙箱、eBPF、技能供应链审核和自动抗体学习。它们属于 P2 或未来工作，不进入当前热路径。
