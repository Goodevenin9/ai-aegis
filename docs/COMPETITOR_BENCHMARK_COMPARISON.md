# AI Aegis 与同类 Agent 安全方案的公开 Benchmark 对比

> 调研日期：2026-09-17。只采用论文/会议正式页面、项目官方结果页、官方仓库和厂商技术文档。这里的“未找到”仅表示截至调研日未发现可公开核验的数据，不代表产品没有内部测试。

## 结论先行

1. **AI Aegis 当前的 AgentHarm 数字有技术价值，但还不能据此宣称领先。** 最终五段管线在公开的 176 harmful + 176 benign 配对集上取得 **90.34% 攻击检出率、16.48% benign FPR、84.57% precision、87.36% F1**；其中硬阻断 harmful 的比例为 **81.25%**。但这是“不执行工具的离线 PreTool 分类/裁决重放”，并且提示词、阈值和策略在同一公开 split 上开发，属于 same-split exploratory optimization，不是 untouched holdout。
2. **AgentDojo 不是竞品，而是端到端攻击/防御 benchmark。** 它的 Targeted ASR、Utility、Utility under attack 衡量 agent 实际跑完轨迹后是否完成攻击/正常任务，不能与 AI Aegis 的检测 recall/FPR 直接相减。
3. **SecureVector 没有可核验的 AgentHarm/AgentDojo 成绩。** 官方仓库公开 `benchmarks/performance_test.py`，内容是性能测试；官网/README 宣称 72 条规则、28 条 agent attack chains 和本地 ML，但未给出 AgentHarm、AgentDojo、ASR、TPR/FPR 的正式结果。因此不能做数字排名。
4. **最接近 AI Aegis 当前“分类检测口径”的公开竞品是 Kaizen，而最接近“真实阻断结果”的是 UBAG。** Kaizen 报告 AgentDojo 100% TPR / 0% FPR，但只有 24 个攻击目标和 4 个手写 benign 样本，且不执行 AgentDojo agent；UBAG 在完整 629-pair AgentDojo `important_instructions` 实验中把 ASR 从 47.7% 降到 0.6%，但它是 Gemini 2.5 Flash 的端到端执行控制，仍不能与 AgentHarm 分类 recall 横比。
5. **公开 AgentHarm 防御论文已经报告了更完整的安全—效用权衡。** ACL 2026 SafeMCP 在 GPT-4o 上报告 harmful Score 0.17、Full Score 0.05、benign Score 0.76、benign Full Score 0.53、benign over-block 0.01。它是逐步在线终止危险动作后的 AgentHarm 原生评分，不是二分类 recall/FPR。
6. **竞争判断：方向有竞争性，证据等级尚未到“领先”。** 90.34% recall 表明语义证据 + 确定性状态机能覆盖大部分显式恶意任务；但 16.48% benign FPR 偏高，且同集调优、无工具执行。现阶段适合对外说“已覆盖 AgentHarm 公共配对集并透明报告 recall/FPR”，不适合说“击败 AgentHarm/AgentDojo/SafeMCP/UBAG”。

## 1. 三类指标不能混为一谈

| 指标 | 真正衡量什么 | 越高/低越好 | AI Aegis 当前是否同口径 |
|---|---|---|---|
| AI Aegis attack detection recall | harmful prompt/候选调用在执行前是否被标为 confirm/block | 高 | 是，本项目自定义离线网关指标 |
| AI Aegis benign FPR | benign 样本是否被错误 confirm/block | 低 | 是；同时另报 hard-block rate |
| AgentHarm Harm/Score | agent 实际轨迹满足每题人工 rubric 条件的平均程度，可得部分分 | 对 harmful 请求越低越安全；对 benign 对照越高越有用 | 否 |
| AgentHarm Full Score | 是否满足完整任务 rubric 的更严格完成度 | harmful 低、benign 高 | 否 |
| AgentHarm refusal / over-block | agent 是否拒绝，或 guard 是否过度中止工作流 | 对 harmful 拒绝高通常更安全；对 benign over-block 低更好 | 仅概念相近，不同实现 |
| AgentDojo Targeted ASR | 注入目标是否在真实、有状态工具轨迹中成功 | 低 | 否 |
| AgentDojo Utility under attack | 遭攻击时原始正常任务是否仍完成 | 高 | 否 |

AgentHarm 的 Harm Score 由每题多个手写条件构成，允许部分得分，LLM judge 只用于狭窄语义条件；论文明确说它不是对整段输出做“有害/无害”二分类。[AgentHarm ICLR 2025 论文](https://proceedings.iclr.cc/paper_files/paper/2025/file/c493d23af93118975cdbc32cbe7323f5-Paper-Conference.pdf)

AgentDojo 官方结果页也明确注明“不是 leaderboard”，因为模型没有在所有 attack/defense 组合上完整运行。[AgentDojo 官方结果页](https://agentdojo.spylab.ai/results/)

## 2. AI Aegis 当前基准结果

数据与运行设置：

- AgentHarm 当前公开配对集：176 harmful + 176 benign，共 352 个样本。
- 运行时间：2026-09-17；AI Aegis commit `d8c907fa6a8e833bffe6cb1af7ce06fc1ea7c577`，worktree clean。
- 模型：`deepseek-v4-flash`，主调用 352 次，聚焦复核 8 次，0 失败。
- 工具执行：关闭；每条任务作为离线 PreTool 网关输入重放。
- 关键污染边界：pipeline defaults、verifier prompt/gate、sequence/radius policy 在同一公开 AgentHarm split 上开发。

| 方案 | Harmful 检出率 | Harmful 硬阻断率 | Benign FPR | Benign 硬阻断率 | Precision | F1 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek direct judge | 89.20% | 89.20% | 17.05% | 16.48% | 83.96% | 86.50% | 1133.9 ms |
| 五段管线 + DeepSeek evidence | 89.20% | 80.11% | 16.48% | 16.48% | 84.41% | 86.74% | 1136.4 ms |
| 五段管线 + focused verifier | **90.34%** | **81.25%** | **16.48%** | **16.48%** | **84.57%** | **87.36%** | 1251.9 ms |

本地可复现证据：[`external_benchmark_report.md`](../reports/agentharm-five-stage-optimized-final-20260917/external_benchmark_report.md) 与 [`external_benchmark_results.json`](../reports/agentharm-five-stage-optimized-final-20260917/external_benchmark_results.json)。上游数据来源：[UK AISI AgentHarm 官方数据集](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)。

### 这组结果能说什么

- 在 352 条公开配对数据上，AI Aegis 能将大多数 harmful 请求在工具执行前识别出来。
- 五段裁决相比 direct judge 略提高 recall/F1，并把部分 harmful 判定降为确认而非直接硬阻断。
- benign FPR 仍为 16.48%（29/176），这是当前最明显的产品竞争短板。

### 不能说什么

- 不能把 `90.34% recall` 写成 `AgentHarm score 90.34%`；两者方向和定义都不同。
- 不能用 `1 - recall = 9.66%` 冒充 AgentHarm ASR/Harm Score；未被网关标记的请求不一定会被下游 agent 成功执行，反过来也一样。
- 不能把 16.48% FPR 直接等同于 SafeMCP 的 1% benign over-block；AI Aegis 的正类包含 confirm/block，而 SafeMCP 统计在线工作流中止/拒绝。
- 不能以 same-split 调优结果宣称未见数据上的泛化性能。

## 3. AgentHarm 原论文：模型基线，不是安全产品成绩

AgentHarm ICLR 2025 原论文采用基础 agent loop、温度 0、最多 4096 输出 token，并用 GPT-4o 对狭窄语义条件和拒绝进行判断。论文表 9 的 public test 结果包括：

| Agent 模型 | 攻击 | Harm Score | Refusal | Benign score（无攻击） |
|---|---|---:|---:|---:|
| GPT-4o | none | 48.4% | 48.9% | 89.9% |
| GPT-4o | universal template | 72.7% | 13.6% | 89.9% |
| Claude 3.5 Sonnet | none | 13.5% | 85.2% | 82.0% |
| Claude 3.5 Sonnet | universal template | 68.7% | 16.7% | 82.0% |
| Gemini 1.5 Pro | none | 15.7% | 78.4% | 64.6% |
| Gemini 1.5 Pro | universal template | 56.1% | 3.5% | 64.6% |

来源：[AgentHarm ICLR 2025 论文，Table 9](https://proceedings.iclr.cc/paper_files/paper/2025/file/c493d23af93118975cdbc32cbe7323f5-Paper-Conference.pdf)。

这些数字展示“未加外部安全层的 agent 模型有多容易完成恶意多步任务”。它们可以作为威胁背景，不能当作 AI Aegis 的直接竞品分数。

## 4. AgentHarm 上的公开防御结果：SafeMCP 及基线 guardrails

ACL 2026 SafeMCP 论文将 guardrail 作为 AgentHarm solver 做逐步在线评测：动作被判危险时，立即终止流程并追加标准拒绝；评测沿用 AgentHarm 的 Score/Full Score，并另报 over-block。论文称训练集与 AgentHarm 评测集分离；其 AgentHarm 7-gram/13-gram overlap 分别为 0.02%/0.00%。

下表摘录同一篇论文 Table 9 的 GPT-4o backbone：

| 防御 | Harmful Score ↓ | Harmful Full ↓ | Benign Score ↑ | Benign Full ↑ | Benign over-block ↓ | Libra Score ↑ |
|---|---:|---:|---:|---:|---:|---:|
| 无额外 guard | 0.51 | 0.34 | 0.79 | 0.54 | 0.00 | 0.72 |
| Llama Guard 3 | 0.02 | 0.01 | 0.60 | 0.40 | 0.31 | 0.72 |
| Qwen3Guard-8B | 0.00 | 0.00 | 0.29 | 0.21 | 0.68 | 0.50 |
| NeMoGuard-8B | 0.12 | 0.09 | 0.53 | 0.35 | 0.38 | 0.66 |
| Lakera ChainGuard | 0.02 | 0.02 | 0.15 | 0.07 | 0.99 | 0.40 |
| AgentMonitor | 0.07 | 0.05 | 0.36 | 0.27 | 0.56 | 0.55 |
| RL-Guard | 0.36 | 0.26 | 0.76 | 0.48 | 0.01 | 0.75 |
| Safiron | 0.45 | 0.33 | 0.79 | 0.54 | 0.03 | 0.72 |
| SafeMCP | **0.17** | **0.05** | **0.76** | **0.53** | **0.01** | **0.83** |

来源：[SafeMCP ACL 2026 正式论文，Table 9 与 evaluation details](https://aclanthology.org/2026.acl-long.522.pdf)。

### 可比性判断

- **可比较到研究目标层面**：双方都希望在 harmful 与 benign 之间取得平衡。
- **不可比较到数值层面**：SafeMCP 的结果是 GPT-4o agent 在线执行后的任务 rubric 得分；AI Aegis 当前只判断输入/候选调用，不生成也不执行完整轨迹。
- SafeMCP 表也说明“接近 0 harmful score”可能由严重过阻获得：例如 ChainGuard 的 benign over-block 为 0.99，Qwen3Guard 为 0.68。因此只看 harmful score 同样会误导。

## 5. AgentDojo 官方结果

AgentDojo 原始版本包含四个有状态环境。官方同一历史配置 `gpt-4o-2024-05-13 + important_instructions` 的结果：

| Defense | Utility | Utility under attack | Targeted ASR ↓ |
|---|---:|---:|---:|
| none | 69.07% | 50.08% | 47.69% |
| `tool_filter` | 72.16% | 56.28% | **6.84%** |
| `transformers_pi_detector` | 41.24% | 21.14% | **7.95%** |
| `spotlighting_with_delimiting` | 72.16% | 55.64% | 41.65% |
| `repeat_user_prompt` | 84.54% | 67.25% | 27.82% |

来源：[AgentDojo 官方结果页](https://agentdojo.spylab.ai/results/)，基准设计与 97 user tasks/629 security tests 来源于[NeurIPS 2024 论文](https://papers.neurips.cc/paper_files/paper/2024/file/97091a5177d8dc64b1da8bf3e1f6fb54-Paper-Datasets_and_Benchmarks_Track.pdf)。

`tool_filter` 的 6.84% 是“攻击最终成功”的比例，不是漏检率；`transformers_pi_detector` 将 ASR 压低的同时大幅牺牲 utility，说明真实竞争点是 ASR 与 utility 的联合 Pareto，而不是单一安全分。

## 6. 产品/厂商公开数据

### 6.1 SecureVector

截至调研日，SecureVector 官方 README 的当前公开说明为 v5.2.0，宣称 72 条规则、28 条 agent-attack chains、可选离线 ML、工具权限和运行时审计。[官方仓库/README](https://github.com/Secure-Vector/securevector-ai-threat-monitor)

但官方仓库的 `benchmarks/` 目录只公开性能测试脚本，没有 AgentHarm、AgentDojo、InjecAgent 或混淆矩阵结果。[官方 benchmarks 目录](https://github.com/Secure-Vector/securevector-ai-threat-monitor/tree/master/benchmarks)

因此：

- AgentHarm：**无公开可核验成绩**。
- AgentDojo：**无公开可核验成绩**。
- Detection recall/FPR：**无公开可核验成绩**。
- 不能根据规则数量推断准确率，也不能把“<5 ms 本地扫描”当作安全效果。

### 6.2 Kaizen Security

Kaizen 官方结果（2026-06-27，Claude Sonnet 4.6 on Amazon Bedrock）报告：

| 数据集 | 样本 | TPR | FPR | F1 |
|---|---:|---:|---:|---:|
| AgentDojo adapter | 28 | 100% | 0.0% | 1.00 |
| InjecAgent adapter | 240 | 100% | 0.0% | 1.00 |
| ASB adapter | 140 | 100% | 0.0% | 1.00 |
| CyberSecEval prompt injection | 251 | 85.56% | 0.8% | 0.9181 |
| 全部 7 组汇总 | 1,066 | 95.72% | 1.31% | 未给汇总 F1 |

来源：[Kaizen 官方 benchmark 文档](https://docs.getkaizen.io/benchmarks/)、[官方结果 JSON](https://github.com/getkaizen/kaizen-evals/blob/main/results/results.json)。

关键限制来自其官方 runner 本身：AgentDojo 的 28 条由 **24 个 injection goal 文本 + 每 suite 1 个手写 benign action（共 4 条）**组成；runner 把 goal 改写为 `The agent carried out: ...` 交给黑盒 detector，未运行 AgentDojo agent、未执行工具、也未覆盖 629 个 attack pairs。[官方 `run_agentdojo.py`](https://github.com/getkaizen/kaizen-evals/blob/main/run_agentdojo.py)

所以这组 100%/0% 是一个很小的静态 action-classification adapter 结果，**不是 AgentDojo 原生 ASR/Utility**。它与 AI Aegis 离线分类口径较接近，但数据集和负样本规模完全不同：28 条 vs 352 条，4 个 benign vs 176 个 benign。

### 6.3 UBAG

UBAG 官方技术页报告 Gemini 2.5 Flash 上的完整 AgentDojo 公司自测：

- `important_instructions`：629 pairs，baseline ASR 47.7% → full-stack ASR 0.6%。
- full stack 的分 suite utility：banking 29.9%、travel 25.0%、slack 32.4%、workspace 45.4%。
- 五种额外攻击共 3,145 full-stack pairs，13 个 residual（0.41%），其中 1 个产生 side effect（0.03%）。
- 厂商明确标注这是 company-run evaluation，不是第三方审计。

来源：[UBAG 官方 benchmark 页面](https://www.ubag.ai/benchmarks)。

这是目前找到的商业方案里证据最接近 AgentDojo 原生端到端定义的一组，但模型、策略、版本和 utility 与 AI Aegis 当前 AgentHarm 离线重放不同，不能直接排名。

## 7. 是否有竞争性

### 有竞争性的部分

- AI Aegis 使用 176/176 的完整公开配对样本，负样本规模远大于 Kaizen 的 AgentDojo adapter（4 个 benign）。
- 报告同时给 recall、hard prevention、FPR、precision、F1、延迟和失败数，证据透明度高于只给单一“拦截率”的厂商材料。
- 90.34% recall 说明产品不是只靠确定性正则；focused verifier 对难例有增益。
- 16.48% FPR 没有被隐藏，且 `always_block` 基线清楚展示了 100% recall 的虚假优势。

### 当前不够有竞争性的部分

- 16.48% benign FPR 对执行网关偏高；若全部作为 hard block，会影响真实可用性。
- 结果使用同一公开 split 调参，证据等级低于独立 holdout 或 blind test。
- 尚无 AgentHarm 原生 Score/Full Score/over-block，无法进入 SafeMCP 类论文的同表比较。
- 尚无完整 AgentDojo ASR + Utility，无法与官方 `tool_filter`、UBAG 等端到端方案比较。
- 纯规则和本地单轮版本在当前 AgentHarm 适配上 recall 为 0%；核心效果依赖 DeepSeek 语义调用，P95 约 1.25 秒。

### 推荐的对外表述

可用：

> 在 AgentHarm 当前公开的 176 harmful / 176 benign 配对集上，AI Aegis 的离线 PreTool 网关取得 90.34% harmful 检出率、16.48% benign FPR 和 87.36% F1。该结果不执行工具，且属于公开 split 上的探索性优化；我们不把它等同于 AgentHarm Harm Score 或 AgentDojo ASR。

不建议：

- “AgentHarm 90.34 分”
- “把 AgentHarm ASR 降到 9.66%”
- “超过 SafeMCP/AgentDojo/UBAG”
- “优于 SecureVector”（对方无公开同口径数字，无法验证）

## 8. 下一轮最小公平对比方案

1. 冻结当前 pipeline，在未参与调参的 split 上报告 recall/FPR/precision/F1，并给 bootstrap 95% CI。
2. 按 AgentHarm 官方 Inspect evaluator 跑真实 agent + proxy tools，报告 harmful Score、Full Score、refusal/over-block、benign Score/Full Score；保留当前 gateway metrics 作为补充。
3. 在固定 AgentDojo version、固定模型和固定 attack 下，分别跑 no defense、AI Aegis 与官方 `tool_filter`；报告 Utility、Utility under attack、Targeted ASR、错误/超时率和成本。
4. 将 `confirm` 与 `block` 分开：对生产可用性，benign hard-block 比“任意 friction FPR”更关键。
5. 对所有竞争结论标注证据级别：学术正式论文、官方可复现 runner、厂商自测、内部 same-split 探索；不要混成一个排行榜。

