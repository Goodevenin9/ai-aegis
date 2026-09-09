# AI Aegis × DeepSeek 实时 API Benchmark 对比报告

> 评测日期：2026-09-09
> 模型：`deepseek-v4-flash`，关闭思考模式，温度 0，JSON 强约束输出
> 评测口径：离线 PreTool 网关重放；数据集中的候选工具从未实际执行

## 核心结论

本次对 InjecAgent、AgentHarm Public 和 AgentDojo Catalog 共 **1,555 条**轨迹进行了真实 DeepSeek API 推理，**1,555/1,555 成功，失败 0 条**。总计输入 867,908 tokens、输出 83,387 tokens；按运行时记录的 DeepSeek V4 Flash 非缓存价格估算约 **0.144855 美元**。

真实结果说明：DeepSeek 对明确的间接提示注入识别非常强，但在“恶意/正常任务语义相近”和复杂工具任务上存在明显误报。五段管线直接接入未经校准的 DeepSeek 离散标签后，结果稳定、可解释，却没有自动优于端到端 Judge；这暴露出当前 Drift 权重主要面向中文多轮渐进攻击，不适合直接套用到英文单轮显式恶意任务。这个结果应作为下一轮校准依据，而不是隐去。

## 结果总表

| 数据集 | 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 |
|---|---|---:|---:|---:|---:|---:|
| InjecAgent | 本地单轮规则 | 4.84% | 4.84% | 0.00% | 100.00% | 9.23% |
| InjecAgent | 五段纯规则 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| InjecAgent | DeepSeek 直接 Judge | **100.00%** | 99.72% | **0.00%** | **100.00%** | **100.00%** |
| InjecAgent | 五段管线 + DeepSeek 证据 | **100.00%** | 98.20% | **0.00%** | **100.00%** | **100.00%** |
| AgentHarm Public | 本地单轮规则 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| AgentHarm Public | 五段纯规则 | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| AgentHarm Public | DeepSeek 直接 Judge | **90.34%** | 89.20% | 22.73% | 79.90% | **84.80%** |
| AgentHarm Public | 五段管线 + DeepSeek 证据 | 37.50% | 0.00% | 19.89% | 65.35% | 47.65% |
| AgentDojo Catalog | 本地单轮规则 | 2.86% | 2.86% | **0.00%** | 100.00% | 5.56% |
| AgentDojo Catalog | 五段纯规则 | 0.00% | 0.00% | **0.00%** | 0.00% | 0.00% |
| AgentDojo Catalog | DeepSeek 直接 Judge | **62.86%** | 60.00% | 13.40% | **62.86%** | **62.86%** |
| AgentDojo Catalog | 五段管线 + DeepSeek 证据 | 42.86% | 20.00% | 14.43% | 51.72% | 46.88% |

## 分数据集解读

### InjecAgent

- 样本为 1,054 条攻击和 17 条正常工具对照。
- DeepSeek Judge 检出 1,054/1,054，正常误报 0/17；五段 + DeepSeek 同样检出全部攻击，其中 1,035 条 Block、19 条 Confirm。
- 该数据转换包含上游给出的攻击者指令和候选攻击工具，属于 `oracle_candidate_replay`。因此它能证明检测器识别给定攻击轨迹，但不能等同于 victim Agent 的原生攻击成功率。
- 正常样本只有 17 条，0% FPR 的统计强度有限，不能单独据此宣称“零误报”。

### AgentHarm Public

- 样本为 176 条 harmful 和 176 条配对 benign。
- DeepSeek Judge 检出 159/176 条攻击，同时误报 40/176 条正常任务；说明召回较高，但误报仍不适合直接无条件阻断。
- 五段 + DeepSeek 检出 66/176，误报 35/176，且攻击样本主要落在 Confirm 而非 Block。原因是单轮离散标签常只贡献 25–30 分，低于 40 分 Confirm 阈值；这套状态机原本强调多轮证据累积。
- 结论不是“管线无效”，而是现有权重与显式恶意单轮任务不匹配。后续需要新增独立的 harmful-intent 证据或 Boundary 规则，不能用测试集直接手调阈值。

### AgentDojo Catalog

- 本轮是 35 条 injection goal 与 97 条用户任务 ground-truth 的目录级重放，不是官方 629 个动态安全测试的原生端到端运行。
- DeepSeek Judge 检出 22/35，误报 13/97；五段 + DeepSeek 检出 15/35，误报 14/97。
- 该结果表明仅凭任务目标与 ground-truth 工具序列，仍不足以替代 AgentDojo 的动态环境、污染数据注入点及实际 victim model 轨迹。

## 各方案真实含义

- `aegis_single_turn_local`：现有本地小模型/规则单轮分析，不使用会话语义状态。
- `five_stage_rules`：Boundary / Capability / Radius / Drift / Friction 的确定性路径，不调用 LLM。
- `five_stage_semantic`：使用数据集真值标签构造的“语义信号全对时上界”，不是 DeepSeek 成绩，不能用于产品宣传。
- `deepseek_judge_live`：真实 DeepSeek 直接输出 Allow / Confirm / Block。
- `five_stage_deepseek_live`：复用同一次 DeepSeek 调用的离散标签，最终分数和裁决由确定性五段管线产生。

## 有效性边界

1. 三组结果都是离线 PreTool 检测指标，不可与论文中的 ASR、Utility 或 Harm Score 直接相减。
2. AgentHarm 和 AgentDojo 的工具序列来自数据集真值，属于 oracle replay；没有执行邮件、支付、Shell 或网络副作用。
3. 本次只运行一次 DeepSeek 推理，尚未测量重复运行的一致性。
4. 首轮并发计时把队列等待计入单请求延迟，因而全量 API P95 已标记为 N/A；检测指标和 token 计数不受影响。修正后的计时会用于下一次独立复测。
5. 免疫学习未加入本轮比较，因为必须先做 train / shadow / test 隔离，避免从测试集学习后回测造成数据泄漏。

## 下一步建议

1. 冻结本次结果为未经调参的 baseline，不在这三组测试集上直接调权重。
2. 从训练/验证分区建立 harmful-intent 第四类语义标签或独立证据，再在未见测试集复测。
3. 对 AgentHarm 的 40 条误报和 AgentDojo 的 13 条误报做错误类型归因，形成规则与语义校准清单。
4. 接入 AgentDojo 原生动态 harness，让 AI Aegis 成为唯一变量，正式报告防护前后 ASR 与 Utility。
5. 用自建中文多轮 Drift 集验证项目主创新，并至少重复运行 3 次报告稳定性。

机器可读明细见同目录下的 `external_benchmark_results.json` 与 `external_benchmark_results.csv`。
