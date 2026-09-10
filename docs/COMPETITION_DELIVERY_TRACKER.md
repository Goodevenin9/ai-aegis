# 参赛交付执行记录

验收日期：2026-09-10。范围覆盖 P0、P1、P2 社区版原型与轻量服务器 Demo。只有附带自动测试、真实启动或机器报告的工作项标记为完成。

| 工作项 | 状态 | 验收证据 |
|---|---|---|
| 模型配置、连接测试、降级状态、调用预算 | 完成 | 真实 DeepSeek 连接 200；密钥可从安全运营页写入并即时生效；状态接口不返回密钥本体与路径（仅末四位掩码）；写入端点无 UI 令牌返回 403；10 次进程预算启动验证 |
| 自然语言路由与受控工具 | 完成 | LangGraph 动态路由；3 个闭集只读工具；参数严格校验；无任意 Shell |
| 会话调查、引用验证、报告导出 | 完成 | 引用必须属于已收集证据；JSON/Markdown 导出；无 UI 令牌返回 403 |
| Benchmark 读取与真实复测 | 完成 | 1,555 条历史真实响应报告；352 条 `v2-explicit-harm` AgentHarm 复测，0 API 失败 |
| 五段管线 `explicit_harm` 意图证据 | 完成 | LLM 只输出布尔标签；状态机固定加权；快照恢复与类型拒绝测试 |
| 插件 → PreTool → 审计链路 | 完成 | Claude Code/Codex 14/14 HTTP E2E；四类插件/UI Node 216/216 |
| 前端中英切换、左侧导航、Agent 时间线 | 完成 | i18n 3,071 个精确词条；17/17 核心词条测试；过程、取消、历史、导出可操作 |
| 记忆治理、证据、RAG 与免疫 | 完成（原型） | TTL/删除/来源、文件限额/脱敏、混合检索、人工激活抗体与风险上限均有测试 |
| 教程、命令、URL、按钮真实性 | 完成 | `aegis-app --install-plugin/--uninstall-plugin` 已实现；安装接口与部署端点均为真实路由 |
| 社区/企业边界及部署手册 | 完成 | P2 规划、自托管手册、Agent 运行手册与验收报告 |
| 干净安装与启动 | 完成 | Wheel 构建并隔离导入 `create_app`（220 routes）；本地真实启动及 DeepSeek Agent 运行通过 |
| Docker 运行 | 条件完成 | 四份 Compose YAML 静态解析通过；本机没有 Docker CLI，须在 Ubuntu 主机执行最终容器启动验收 |

## 必须保留的诚实边界

- 哈希链提供事后文件篡改可发现性，不防止已控制进程内存的攻击者。
- 外部 benchmark 是离线 PreTool 网关回放，不是上游原生 Agent ASR。
- `five_stage_semantic` 是真值标签上界，不是模型实测。
- `deepseek_judge_live` 与 `five_stage_deepseek_live` 复用同一次响应，因此不是独立提示词基线。
- AgentHarm `v2-explicit-harm` 达到 95% 检出，但确认口径误报为 53%；该结果证明仍需独立校准集，不能宣传为优于端到端 Judge。
- OCR 在 Docker 镜像中安装中英文 Tesseract；当前 Windows 主机没有 Tesseract，因此只完成自动化适配器测试，容器 OCR 仍需 Ubuntu 运行验收。
- 当前可交付级别是本科竞赛/单机社区版与轻量 Demo，不等同于具备 SSO、RBAC、多租户 PostgreSQL、对象存储和高可用队列的企业生产版。
