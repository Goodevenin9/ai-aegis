# AI Aegis 参赛交付与验收报告

## 1. 交付结论

AI Aegis 已形成可运行的“Agent 实时防护 + 会话级分析 + 安全运营 Agent”社区版原型。系统不是聊天壳：插件在工具执行前调用五段管线，行为写入哈希链审计；运营侧可接入文档、表格、PDF、Word 和截图证据，进行 RAG 检索、会话调查、报告导出、记忆治理及人工审批的免疫学习。

当前版本适合互联网+等本科竞赛现场演示、代码审查和单机/轻量服务器 Demo。企业版所需的多租户、SSO/RBAC、高可用任务队列、对象存储、恶意文件扫描和集中审计仍明确列为产品化工作，未用占位按钮冒充完成。

## 2. 核心工程能力

### P0：实时执行前防护

- Boundary：中文归一化、零宽/全角混淆、高危 Shell、敏感路径与确定性红线。
- Capability：结构化工具能力与会话 Manifest 精确比对。
- Radius：项目、本机、用户、系统与外网影响范围判定。
- Drift：会话状态机累计主题偏移、权限试探、请求升级、明确有害目标、重复重试和免疫匹配。
- Friction：固定阈值融合原有判定和各层信号，输出 `allow / confirm / block`；无人值守时 `confirm` 升级为 `block`。
- LLM 只提取闭集布尔/枚举证据，不返回风险分数；状态转移和裁决由确定性代码负责。

### P1：会话、策略与可评测性

- `traceId` 串联 Prompt、工具调用与审计事件，形成会话时间线和漂移曲线。
- 持久化能力 Manifest、阈值配置、信任授权、哈希链校验和运行时策略。
- 自建中文数据集与外部公开 benchmark 回放，输出 JSON、CSV、Markdown、实现指纹和数据来源哈希。
- Claude Code、Codex、Copilot CLI、Cursor 与 OpenClaw 插件/适配器；CLI 安装命令和 UI 安装 API 均有真实实现。

### P2：安全运营系统

- LangGraph 受控工作流按知识查询、事件调查、数据集评测和策略变更动态路由。
- DeepSeek 超时、重试、并发上限、进程调用预算、用量/失败/延迟状态和确定性降级。
- 闭集只读工具：读取证据、读取会话时间线、验证哈希链；Agent 无任意 Shell 或动态工具注册权限。
- TXT/Markdown/日志/YAML、JSON/JSONL、CSV/TSV、PDF、DOCX 和截图 OCR；大小、页数、像素、超时、去重及敏感信息脱敏。
- BM25 + 哈希向量混合检索、章节切片、重排、文档类型过滤、可追溯引用、Recall@K/MRR 评测。
- Candidate → Shadow → Active → Decaying → Retired 免疫生命周期；只有人工批准的 Active 抗体影响 Drift，且单会话贡献封顶，不能独立 Block。
- 受治理长期记忆具有类型、来源、确认状态、TTL 和删除能力。
- 策略变更先模拟，再按提案哈希人工审批并幂等应用；模型不能自行修改执行策略。

## 3. 自动化与真实运行证据

| 验收项 | 结果 |
|---|---:|
| Python 默认测试集 | 1060 通过 / 6 条件跳过 / 0 失败 |
| Claude Code + Codex 插件 HTTP E2E | 14 / 14 通过 |
| 四类插件与 UI Node 测试 | 216 / 216 通过 |
| i18n 核心词条 | 17 / 17 通过（词典共 3,071 个精确词条） |
| 真实 DeepSeek Agent 冒烟 | 在线、3 次调用、0 失败、无离线降级 |
| HTTP 启动验收 | `/health`、模型测试、工具目录、benchmark、Agent、导出均成功 |
| 敏感写接口 | 无本地 UI 令牌启动 Agent/导出均为 403 |
| Wheel | `ai_aegis-1.0.0-py3-none-any.whl`，隔离安装后 `create_app` 产生 220 条路由 |
| Compose | 4 份 YAML 静态解析通过；本机缺 Docker，服务器运行验收待执行 |

Python 的 191 个 deselected 是 `pyproject.toml` 明确排除的 integration 标记；其中关键插件 E2E 已用覆盖参数单独执行。6 个 skip 来自可选依赖/平台条件，不计作通过。

## 4. Benchmark 结论

历史全量报告包含 InjecAgent 1,071、AgentHarm Public 352、AgentDojo Catalog 132，共 1,555 条。真实 DeepSeek 响应 1,555/1,555 成功：

| 数据集 | DeepSeek-Judge 检出/FPR | 五段+DeepSeek 检出/FPR |
|---|---:|---:|
| InjecAgent | 100% / 0% | 100% / 0% |
| AgentHarm Public（旧六字段） | 90% / 23% | 38% / 20% |
| AgentDojo Catalog | 63% / 13% | 43% / 14% |

为修复 AgentHarm 只包含“有害原始目标”、没有主题漂移的问题，新增 `explicit_harm` 离散证据后，单独真实复测 352 条：API 失败 0，估算成本 0.045613 美元；DeepSeek-Judge 为 95%/38%，正确叠加原判定后的五段管线为 95%/53%。这不是好于 Judge 的结果：五段管线额外把部分高风险合法任务送入 `confirm`，提高了人工复核量。参赛陈述应强调它提升的是会话状态、确定性控制和可解释性，而不是声称在该静态数据集上全面超过端到端 Judge。

下一次模型校准必须先固定独立 validation/test 切分，在 validation 上调标签定义和阈值，test 只运行一次。免疫学习同样必须使用 train → shadow → test 隔离，禁止拿测试真值生成抗体。

## 5. 社区版与企业版取舍

| 能力 | 社区版（本次交付） | 企业版（产品化） |
|---|---|---|
| 实时检测 | 本地规则、Guardian、五段管线、单机插件 | 中央策略编排、灰度发布、组织级例外 |
| 会话分析 | SQLite、单机 trace/Drift/哈希链 | PostgreSQL、跨设备关联、长期留存 |
| 安全 Agent | 本机 LangGraph、闭集只读工具、人工审批 | 独立 Worker、队列、租户配额、SLA |
| 证据/RAG | 本地文件、OCR、混合检索 | 对象存储、恶意文件扫描、企业知识权限继承 |
| 免疫学习 | 本机候选/影子/人工激活 | 签名抗体分发、组织级灰度与回滚 |
| 身份权限 | 本地 UI 令牌、单组织轻控制平面 | SSO、RBAC、审批链、审计管理员 |
| 集成 | 本地插件、CSV/基础 SIEM | 工单、SOC/SIEM、Webhook、合规留存策略 |

## 6. 演示顺序

1. 在“会话安全”页展示安全 `Read README` 为 Allow、高危命令为 Boundary Block。
2. 连续执行权限试探，展示 Drift 分数与时间线增长。
3. 在“安全运营”上传制度 PDF/Word/截图并检索，展示引用而非无来源回答。
4. 输入自然语言调查请求，展示 LangGraph 路由、节点轨迹、模型在线/降级状态和导出报告。
5. 创建免疫候选，演示 Shadow 不影响判定、人工批准 Active 后只增加受限风险分。
6. 展示 benchmark 机器报告，同时主动说明离线回放、共享响应与 AgentHarm 误报边界。

## 7. 启动与部署

Windows 本地真实模型启动：

```powershell
D:\pyt\python.exe scripts/start_security_demo.py `
  --key-file 'C:\secure\deepseek-key.txt' --port 8741 --max-model-calls 200
```

Ubuntu 轻量容器：

```bash
export AEGIS_AGENT_KEY_FILE=/opt/ai-aegis/secrets/deepseek.key
docker compose -f docker-compose.demo.yml -f docker-compose.agent.yml up -d --build
docker compose -f docker-compose.demo.yml -f docker-compose.agent.yml ps
curl --fail http://127.0.0.1:8741/health
```

镜像为页面可见能力安装 LangGraph、PDF、DOCX、Pillow 和中英文 Tesseract。更完整的反向代理、控制平面、密钥及备份步骤见 `SECURITY_AGENT_RUNBOOK.md` 与 `SELF_HOSTED_CONTROL_PLANE.md`。

## 8. 发布门槛

- 禁止提交 DeepSeek Key、`.env.self-host`、管理员密钥或 UI 令牌。
- 必须保留 Apache-2.0、NOTICE 与第三方规则归属；品牌清理不等于删除法律归属。
- 在 Ubuntu 执行容器构建、OCR 中文样例、重启恢复和 768MB 限制下的运行验收后，才可把“服务器容器部署”标为完全通过。
- 对外数字必须引用机器报告哈希，且不得把离线检出率描述成原生 ASR。
