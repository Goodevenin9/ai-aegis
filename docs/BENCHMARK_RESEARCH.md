# AI Aegis Agent 安全 Benchmark 选型研究

> 调研日期：2026-09-08
> 来源边界：仅使用论文、作者/组织官方仓库、官方数据集卡与许可证。
> 目标：为 AI Aegis 的 Boundary / Capability / Radius / Drift / Friction 五段管线建立可复现的第三方评测，同时避免把不同口径的数字误写成“同榜对比”。

## 结论

第一批实际接入建议采用三个 benchmark：

1. **InjecAgent（全量 1,054 例）**：数据是易转换的 JSON/JSONL，最适合先验证“外部工具返回内容被注入后，攻击者诱导调用另一工具”的 Boundary、Capability 和 Radius 检测。
2. **AgentDojo（v1 Workspace 子集，随后扩至四套件）**：最适合验证真实的有状态、多工具轨迹以及安全性与任务效用之间的权衡；它应成为最终最有说服力的端到端基准。
3. **AgentHarm（公开 harmful + benign 配对集）**：补足显式恶意、多步骤工具任务和正常负样本，用于验证“不能靠全部拒绝获得高安全分”。其许可证有限定，只能用于提升 AI 系统安全与安保。

**ASB 暂不进入第一批全量运行**。它非常适合第二批验证 Memory Poisoning、PoT Backdoor 与免疫学习，但原生框架依赖 AIOS、Python 3.11 和模型运行，接入成本明显高于静态 JSONL 回放；本轮可先做小型兼容性 smoke test，待前三个基准口径稳定后再接入全量。

没有一个上述 benchmark 能完整覆盖 AI Aegis 主打的“中文多轮、逐步权限爬升”场景：InjecAgent 明确是模拟的单轮工具输出注入；AgentDojo 是一个任务内的多工具状态轨迹；AgentHarm 是多步骤恶意任务，但不是中文渐进式多轮对话。因此，**第三方 benchmark 不能替代项目自建中文 Drift 数据集**，两者应并列报告。[AgentDojo 论文对 InjecAgent 单轮性质的说明](https://arxiv.org/html/2406.13352#S2)、[AgentHarm 论文对多步骤 Agent 任务的定义](https://arxiv.org/html/2410.09024)

## 统一评测合同

### 两种模式必须分开

**A. 离线安全网关回放（本轮优先）**

- 将上游 benchmark 的用户意图、工具返回、候选工具调用和目标工具序列转换为 AI Aegis 的标准事件。
- 只执行检测逻辑，不执行真实外部副作用。
- 比较 AI Aegis 单轮规则基线、DeepSeek Judge、五段管线（无免疫）和五段管线（有免疫）。
- 主要指标是检测召回、阻断率、确认率、正常样本误报率和延迟。

**B. 原生端到端 Agent 运行（下一步）**

- 在同一 victim model、同一攻击、同一任务/版本和相同随机设置下，让 Agent 实际规划并调用沙箱工具。
- AI Aegis 作为 PreTool 防护层嵌入原生 harness。
- 报告 benchmark 原生的攻击成功率、任务效用以及启用防护后的效用变化。

离线模式回答“AI Aegis 能否识别/拦截给定危险行为”；端到端模式回答“攻击者最终能否诱导这个 Agent 完成攻击”。两者不可混写。

### 标准事件映射

每个适配器至少输出：

```json
{
  "benchmark": "injecagent",
  "case_id": "...",
  "trace_id": "benchmark:case-id",
  "turn_index": 0,
  "event_type": "before_tool_call",
  "user_intent": "原始用户任务",
  "untrusted_observation": "工具返回中的不可信内容",
  "tool_name": "候选工具名",
  "tool_input": {},
  "allowed_capabilities": [],
  "allowed_scope": {},
  "expected_label": "malicious",
  "metadata": {
    "attack_type": "...",
    "source_split": "...",
    "source_license": "..."
  }
}
```

原始数据必须只读保存；转换数据记录上游仓库、版本或 commit SHA、文件路径和转换器版本。对含攻击文本的数据，不进入训练集、不生成免疫抗体，除非另行划分 train/shadow/test，防止评测污染。

## 候选对比

| Benchmark | 上游规模与任务 | 公开数据形态 | 许可证 | 与 PreTool/会话回放兼容度 | 第一批建议 |
|---|---|---|---|---|---|
| AgentDojo | 原论文 97 个真实任务、629 个安全测试；4 个有状态环境、74 个工具 | Python 任务类、YAML 环境、结构化消息和 tool-call trace | MIT | 高，但端到端适配成本中高 | Workspace 子集优先，随后全套件 |
| InjecAgent | 17 个用户工具 × 62 个攻击者场景 = 1,054 例；直接伤害与数据窃取 | JSON/JSONL，含用户指令、工具参数、被污染工具返回、攻击工具 | MIT | **最高**，静态转换简单；本质为单轮 | **全量接入** |
| AgentHarm | 论文 110 个独特恶意任务、加增强共 440；当前公开集只开放其中一部分，并提供 benign 对照 | JSON，含 prompt、target_functions、grading_function | MIT + 仅限改善 AI 安全/安保的附加条款 | 中；有目标工具序列，但完整分数依赖 Inspect 和 judge | 公开 harmful + benign 配对集 |
| ASB | 最新论文版本：10 场景、10 Agent、400+ 工具与任务、27 类攻击/防御、7 个指标 | JSONL 数据 + AIOS 运行框架 | MIT | 中高；覆盖面广但原生运行较重 | 第二批，先 smoke test |

规模与设计来源：[AgentDojo 论文](https://arxiv.org/html/2406.13352)、[InjecAgent 论文统计表](https://arxiv.org/html/2403.02691#S3.SS1)、[AgentHarm 论文](https://arxiv.org/html/2410.09024)、[AgentHarm 官方数据集卡](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)、[ASB 最新论文版本](https://arxiv.org/html/2410.02644)。

## 1. AgentDojo

### 为什么适合 AI Aegis

AgentDojo 的环境是有状态的，Agent 必须动态执行多个工具调用；用户任务和攻击任务分别有确定性 utility/security 检查，检查可基于环境前后状态和函数调用轨迹，而不是单纯让另一个 LLM 打分。这与 AI Aegis 的 traceId 会话重建、Capability/Radius 边界和 Drift 累积最匹配。[论文设计](https://arxiv.org/html/2406.13352#S3)、[官方 TaskSuite 轨迹检查实现](https://github.com/ethz-spylab/agentdojo/blob/main/src/agentdojo/task_suite/task_suite.py)

原论文报告 4 个环境（Workspace、Slack、Travel Agency、e-banking）、97 个用户任务、629 个安全测试和 74 个工具。[论文数据概览](https://arxiv.org/html/2406.13352#S3.SS1)

当前代码将任务定义为 Python 类、环境保存在 YAML 中，运行日志中的 assistant message 带 `tool_calls`，工具响应带对应调用与内容；官方代码会从消息中抽取函数调用堆栈并进行 utility/security 判定。[官方任务套件代码](https://github.com/ethz-spylab/agentdojo/blob/main/src/agentdojo/task_suite/task_suite.py)、[官方任务示例](https://github.com/ethz-spylab/agentdojo/blob/main/src/agentdojo/default_suites/v1_2_2/banking/user_tasks.py)

### 数据下载与许可证

- 可通过 `pip install agentdojo` 或官方 GitHub 仓库离线安装；API 仍在开发，评测必须固定版本。[官方 README](https://github.com/ethz-spylab/agentdojo)
- 仓库采用标准 MIT License。[官方 LICENSE](https://github.com/ethz-spylab/agentdojo/blob/main/LICENSE)

### 官方基线

官方结果页明确说它**不是排行榜**，因为不同模型并未在所有攻击和防御组合上运行。以同一历史配置 `gpt-4o-2024-05-13` 为例：无防御 + `important_instructions` 的 Utility 69.07%、攻击下 Utility 50.08%、Targeted ASR 47.69%；`tool_filter` 防御下分别为 72.16%、56.28%、6.84%。这些数字只能作为复现实验的目标配置，不能直接与 AI Aegis 离线检测率比较。[官方结果页](https://agentdojo.spylab.ai/results/)

### 五段管线映射

- Boundary：扫描不可信 tool output 中的直接/变形注入。
- Capability：比较原始用户任务所需工具与攻击目标工具。
- Radius：根据工具参数与环境状态判断是否越出原任务对象、账户或接收人。
- Drift：累计一个任务内的多次读取、搜索、外发和重试轨迹。
- Friction：输出 allow/confirm/block，并分别统计攻击阻断与正常任务效用损失。

### 限制

- 原生分数依赖 Agent 实际运行；把 ground-truth 或完整 trace 直接回放给 Aegis，只能产生网关检测指标。
- 不同 AgentDojo 版本的任务和 API 会变化；没有固定版本的数字不可比较。
- 一个任务内的多步工具轨迹不是中文多轮渐进诱导。

## 2. InjecAgent

### 为什么适合 AI Aegis

InjecAgent 专门评估工具集成 Agent 的间接提示注入。它由 17 个正常用户工具与 62 个攻击者场景笛卡尔积生成 1,054 个测试，攻击分为直接伤害和数据窃取；数据窃取还分数据获取 S1 与数据外传 S2。[论文统计](https://arxiv.org/html/2403.02691#S3.SS1)、[官方 README](https://github.com/uiuc-kang-lab/InjecAgent)

公开样本已经包含：`User Instruction`、`User Tool`、`Tool Parameters`、带攻击文本的 `Tool Response`、`Attacker Tools`、`Attacker Instruction`、`Expected Achievements` 和 `Attack Type`。这几乎可以一一映射到意图流、工具观察和候选 PreTool 调用。[官方 direct-harm 数据样本](https://github.com/uiuc-kang-lab/InjecAgent/blob/main/data/test_cases_dh_base.json)、[原始 JSON](https://raw.githubusercontent.com/uiuc-kang-lab/InjecAgent/main/data/test_cases_dh_base.json)

### 数据下载与许可证

- 官方仓库直接提供 base/enhanced 的 direct-harm 与 data-stealing JSON，以及 user/attacker JSONL 和工具定义，可离线下载。[官方数据目录](https://github.com/uiuc-kang-lab/InjecAgent/tree/main/data)
- 仓库及数据采用标准 MIT License。[官方 LICENCE](https://github.com/uiuc-kang-lab/InjecAgent/blob/main/LICENCE)

### 官方基线

论文报告 ReAct prompted GPT-4 在 base 设置 ASR 为 24%，加入额外 hacking prompt 的 enhanced 设置升至 47%。论文还分别报告 ASR-valid 与 ASR-all；复现时必须保留这一区分。[论文结果](https://arxiv.org/html/2403.02691#S4)、[官方评测输出定义](https://github.com/uiuc-kang-lab/InjecAgent#output)

### 五段管线映射

- Boundary：检测不可信工具返回中的攻击指令和增强型 hacking prompt。
- Capability：`User Tool` 是初始允许能力，`Attacker Tools` 是候选越权能力，适合精确集合比较。
- Radius：将锁、邮件、医疗、金融、外发等工具按 local/project/external/敏感对象映射影响域。
- Drift：原始数据是单轮，不能声称验证真实状态漂移；只能把 S1→S2 作为有限的两阶段链条实验。
- Friction：对攻击样本统计 confirm/block，对正常用户工具调用另建 benign control，避免“全部拦截”的伪高分。

### 限制

- InjecAgent 论文强调的是 victim Agent 是否执行攻击；我们的静态回放并不调用同一个 victim model，因此检测召回不能与其 24%/47% ASR 相减或宣称“提升了多少百分点”。
- 数据本身没有完整自然发生的多轮 trace。若用 `Attacker Tools` 生成候选调用，必须在报告中标注为 **oracle candidate replay**，不能称为原生 Agent 运行。

## 3. AgentHarm

### 为什么适合 AI Aegis

AgentHarm 衡量 Agent 对显式恶意、多步骤任务的服从和执行能力。论文设计包含 110 个独特恶意任务及 330 个增强变体，覆盖 11 类危害，并为同主题任务构造 benign 版本以分离“安全拒绝”与“Agent 根本不会做任务”。[论文概述](https://arxiv.org/html/2410.09024)、[benign 设计](https://arxiv.org/html/2410.09024#S3.SS3)

当前官方数据集卡说明，公开数据并非论文全集：当前开放 44/66 个 public test 基础行为（176 个增强样本）和 8/11 个 validation 基础行为（32 个增强样本），并同时提供 harmful、harmless_benign 与 chat 配置。[官方数据集卡](https://huggingface.co/datasets/ai-safety-institute/AgentHarm/blob/main/README.md)

公开 JSON 的关键字段为 `id`、`name`、`category`、`prompt`、`target_functions`、`grading_function`，并标明 detailed/open-ended 与是否带 hint。`target_functions` 很适合转换为 Capability 序列和 Radius 扩张链。[官方 harmful JSON](https://huggingface.co/datasets/ai-safety-institute/AgentHarm/blob/main/benchmark/harmful_behaviors_test_public.json)、[官方 benign JSON](https://huggingface.co/datasets/ai-safety-institute/AgentHarm/blob/main/benchmark/benign_behaviors_test_public.json)

### 数据下载与许可证

- 文件可从官方 Hugging Face 数据集仓库离线下载，代码由 UK AI Security Institute 的 Inspect Evals 提供。[官方数据集](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)、[官方 Inspect Evals 实现](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/agentharm)
- 许可证不是无条件 MIT：附加条款禁止将数据集和 benchmark 用于“改善 AI 系统安全与安保”以外的目的。AI Aegis 安全评测符合该目的，但再分发时必须保留许可证，且不应把样本用于通用模型训练。[官方 LICENSE](https://huggingface.co/datasets/ai-safety-institute/AgentHarm/blob/main/LICENSE)
- 数据集作者要求仅用于评测，并提供 canary GUID 用于监控训练污染。[官方数据集卡](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)

### 官方基线

原论文全集上，无 jailbreak 的 GPT-4o harm score 为 48.4%、refusal 48.9%；通用 jailbreak template 下 harm score 升至 72.7%、refusal 降至 13.6%。当前公开子集的数据分布已变化，数据集卡提示 GPT-4o 直接请求平均 harm score 由论文的 48.4% 变成 54.9%，因此必须明确写“公开子集复现”，不能冒充论文全集结果。[论文基线](https://arxiv.org/html/2410.09024#S4)、[公开集差异说明](https://huggingface.co/datasets/ai-safety-institute/AgentHarm/blob/main/README.md)

### 五段管线映射

- Boundary：显式恶意任务、敏感对象、已知高危动作。
- Capability：把 target function 序列与任务 manifest 比较，检测越权工具。
- Radius：邮件群发、社交发布、转账、下载与跨平台操作体现影响半径扩张。
- Drift：一个任务的 target function 是多步骤链，但公开静态数据没有真实模型逐轮产生的调用；只能在 oracle replay 中测试状态机累积。
- Friction：harmful 与 benign 配对可衡量安全性和可用性，避免 always-block 基线看似安全。

### 限制

- AgentHarm 的完整 harm score 由工具执行结果、拒绝判断和语义 judge 共同产生；官方默认 judge 可需要模型 API。只回放 target function 时不能复现 harm score。[官方运行参数](https://ukgovernmentbeis.github.io/inspect_evals/evals/agentharm/)
- 数据包含明显有害内容，应只在隔离评测目录处理；任何工具均必须 mock，禁止连接真实邮件、支付、社交平台或 Shell。

## 4. ASB（第二批）

ASB 最新论文版本覆盖 10 个场景、10 个 Agent、400+ 工具和任务、27 类攻击/防御及 7 个指标，攻击面包含 Direct/Observation Prompt Injection、Memory Poisoning、Plan-of-Thought Backdoor 和 Mixed Attack。这对 AI Aegis 的意图流、长期记忆和免疫学习验证非常有价值。[ASB 论文](https://arxiv.org/html/2410.02644)、[官方仓库](https://github.com/agiresearch/ASB)

官方数据目录含正常工具、攻击工具、aggressive/non-aggressive 指令和 agent task JSONL；例如攻击工具样本直接提供 `Attacker Tool`、`Attacker Instruction`、`Attack goal`、`Attack Type` 与目标 Agent，静态适配并不困难。[官方数据目录](https://github.com/agiresearch/ASB/tree/main/data)、[攻击工具样本](https://github.com/agiresearch/ASB/blob/main/data/all_attack_tools_aggressive.jsonl)

但原生运行基于 AIOS，README 推荐 Python 3.11，并需要云模型或 Ollama；全套实验横跨 13 个模型，论文报告的最高平均 ASR 为 84.30%。这一数字是 Agent 攻击成功率，不是 Aegis 检测率。[官方运行说明](https://github.com/agiresearch/ASB#%EF%B8%8F-getting-started)、[论文结果](https://arxiv.org/html/2410.02644#S5)

仓库采用标准 MIT License。[官方 LICENSE](https://github.com/agiresearch/ASB/blob/main/LICENSE)

建议第一批只抽取：

- normal/aggressive 工具各一小组，验证 Capability 与误报；
- observation injection 样本，验证 Boundary；
- memory poisoning 样本，验证记忆进入 Agent 前是否被标记为不可信；
- 不把 smoke-test 结果写成 ASB 官方全量成绩。

## 基线与指标设计

### 同口径内部基线

每个转换后的样本应同时跑：

1. `aegis_single_turn`：AI Aegis 单轮规则/模型判定。
2. `deepseek_judge_live`：真实调用固定版本 DeepSeek Judge；若没有 API Key，结果必须标记 `not_run`，不得使用数据集中预存标签冒充调用结果。
3. `aegis_five_stage_no_immune`：五段管线，关闭免疫贡献。
4. `aegis_five_stage_immune`：五段管线，使用仅从训练/历史分区生成并经 Shadow/批准的抗体。
5. `always_allow` 与 `always_block`：作为 sanity baseline，显示只追求安全或只追求效用的极端结果。

### 统一指标

- Attack Detection Recall：攻击样本中 `confirm + block` 的比例。
- Hard Prevention Rate：攻击样本中 `block` 的比例。
- Confirmation Rate：所有样本中 `confirm` 的比例。
- Benign False Positive Rate：正常样本中 `confirm + block` 的比例。
- Benign Hard-Block Rate：正常样本中 `block` 的比例。
- Precision / Recall / F1 / Balanced Accuracy。
- Median、P95、P99 决策延迟。
- 每层命中率：Boundary、Capability、Radius、Drift、Immune、upstream base verdict。
- First Detection Turn：对于真实轨迹，第一次 confirm/block 出现在哪一轮。
- Decision Stability：同一样本重复运行的一致率；纯规则路径应为 100%。
- LLM Calls / Token / Cost：DeepSeek 基线和 Drift 标签提取分别记录。

### Drift 与免疫的独立指标

- 链条开始时的分数、每轮增量、最终分数。
- 在达到攻击工具前是否已 confirm/block。
- 重复重试处罚是否生效。
- 抗体命中率、Shadow 误报率、Active 增益。
- 使用严格 train/shadow/test 分区报告免疫开启前后差值。
- 抗体不能从 test 样本学习后再回测同一 test，否则属于数据泄漏。

## 哪些数字不能直接比较

| 上游数字 | 不能直接对比的 Aegis 数字 | 原因 |
|---|---|---|
| AgentDojo Targeted ASR | 离线 block/detection rate | 前者需要 victim Agent 实际完成攻击目标，后者只看网关决策 |
| AgentDojo Utility | benign allow rate | Utility 检查任务是否真正完成，Allow 只说明网关没有阻止 |
| InjecAgent ASR-valid / ASR-all | Aegis recall | 上游包含 victim model 工具选择能力，且 valid 分母不同 |
| AgentHarm harm score / refusal | Aegis block rate | harm score 依赖任务执行和 judge；Block 不等于模型拒绝 |
| ASB ASR / refusal / NRP | Aegis detector F1 | ASB 是 Agent+攻击+防御的整体系统指标 |

只有在**相同 benchmark 版本、相同 victim model、相同攻击、相同样本、相同工具环境和同一随机种子策略**下，将 AI Aegis 作为唯一变化因素接入原生 harness，才可以报告“ASR 从 X 降至 Y、Utility 从 A 变为 B”。

## 实施优先级与交付建议

### 第一批：可在当前 P2 评测框架中完成

1. 下载并固定上游版本与许可证快照。
2. 写 InjecAgent adapter，全量转换 1,054 例。
3. 从 InjecAgent user cases 构造无攻击的对应 benign controls。
4. 写 AgentHarm adapter，使用公开 harmful/benign 配对数据；静态 `target_functions` 回放明确标记 `oracle_replay`。
5. 写 AgentDojo trace adapter，先固定 v1 Workspace 子集；仅使用 mock 环境与官方 trace schema。
6. 运行五个内部基线并导出 JSON、CSV、Markdown 表格。
7. 所有报告同时给出样本数、跳过数、错误数、版本、配置 hash、时间与环境。

### 第二批：端到端与扩展

1. 将 AI Aegis PreTool hook 插入 AgentDojo 原生 FunctionsRuntime，报告 ASR、Utility 和 Utility-under-attack。
2. 用固定 victim model 至少重复 3 次，报告均值和离散程度。
3. 接入 ASB 的 OPI 与 Memory Poisoning 子集，再扩至全量。
4. 将自建中文多轮集与第三方结果并列，而非混合成一个总分。

## 最终推荐的展示方式

对外只做两张主表：

1. **第三方离线安全检测表**：三个 benchmark 上的 Recall、FPR、F1、P95 latency，比较 上游原版 / DeepSeek Judge / 五段管线 / 五段管线+免疫。
2. **AgentDojo 端到端表**：同一 victim model 下的 Targeted ASR、Utility、Utility under attack，比较无防护 / AgentDojo tool filter / AI Aegis。

另附一张“中文多轮 Drift 专项表”，强调第三方 benchmark 的缺口和 AI Aegis 自建数据集的必要性。这样既有国际公开 benchmark 的可比性，也不会用错误口径夸大效果。
