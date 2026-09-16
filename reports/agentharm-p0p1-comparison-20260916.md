# AI Aegis P0/P1 AgentHarm 双模式复测报告

## 测试范围

- 数据集：AgentHarm public test，176 个 harmful + 176 个 benign，共 352 个样本。
- 模型：`deepseek-v4-flash`，温度 0。
- 执行方式：离线 PreTool 重放；候选工具从未实际执行。
- API：两种证据模式在最终运行中各新增调用 352 次，失败样本均为 0；密钥仅从本地文件读取，未写入报告。无 `explicit_harm` 模式估算费用 0.047770 美元，含 `explicit_harm` 模式估算费用 0.049733 美元。
- 受控消融：两种模式使用相同分类准则、相同模型参数和相同样本，只改变输出 schema 是否包含 `explicit_harm`。
- 指标边界：这里衡量 AI Aegis 网关的检测/干预结果，不能直接等同于 AgentHarm 上游的原生 ASR 或 harm score。
- 验证性质：这是基于此前误报分析完成提示词与阈值校准后的同集复测（post-calibration re-evaluation），不是未参与调参的 untouched holdout，不能作为泛化性能的单独证明。

## 最终结果

| 证据模式 | 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | 正常确认率 | 正常硬阻断率 | Precision | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 不含 `explicit_harm` | DeepSeek Judge | 89.77% | 89.77% | 19.32% | 1.14% | 18.18% | 82.29% | 85.87% |
| 不含 `explicit_harm` | 五段管线 + DeepSeek 证据 | 8.52% | 0.00% | 7.39% | 7.39% | 0.00% | 53.57% | 14.71% |
| 含 `explicit_harm` | DeepSeek Judge | 88.07% | 88.07% | 18.18% | 3.41% | 14.77% | 82.89% | 85.40% |
| 含 `explicit_harm` | 五段管线 + DeepSeek 证据 | 42.61% | 0.57% | 11.93% | 11.93% | 0.00% | 78.12% | 55.15% |

## P0/P1 修复结论

1. 修复了同一次 DeepSeek 响应既作为 Judge 裁决、又作为语义证据进入 Friction 的重复计分。
2. 单个 LLM 标签不再直接制造用户摩擦；需要两个独立语义信号、重复证据或确定性规则共同达到阈值。
3. LLM 推断出的未声明能力只作为风险证据；结构化工具调用真实越出 Manifest 时仍会立即要求确认。
4. 无新增风险的安全轮次会衰减 Drift，并中断重复攻击连击。
5. 报告把正常确认与正常硬阻断分开，避免把“提醒”和“错误阻断”混成一个数字。

与仓库中修复前的 `external-benchmarks-explicit-harm` 结果相比，含 `explicit_harm` 的五段方案正常误报率从 52.84% 降至 11.93%，正常硬阻断率从 33.52% 降至 0%。代价是攻击检出率从 95.45% 降至 42.61%，说明本次修复明确选择了降低误阻、要求证据堆叠，而不是追求激进拦截。由于模型提示词也经过校准，这组前后对比用于说明工程取舍，不是单变量因果实验。

## 应如何解读

- `explicit_harm` 对 AgentHarm 的语义检出有明显贡献：移除后，保守五段管线几乎只处理确定性越界。
- 直接 DeepSeek Judge 在此数据集上的召回和 F1 更高，但仍会硬阻断 13% 左右的正常样本。
- 五段管线的价值不是在单轮 AgentHarm 上“击败大模型”，而是提供确定、可复现、低误阻的执行控制；其核心优势应继续用多轮漂移、重复试探和权限爬升数据集验证。
- 当前五段方案在 AgentHarm 上硬阻断率为 0%，意味着仅靠一次 LLM 语义判断不会直接阻断。生产上可通过 `balanced` / `strict` 策略档位按场景调整，但不应隐瞒安全性与可用性的取舍。

## 可复现文件

- 含 `explicit_harm`：`reports/agentharm-p0p1-final-explicit-harm-20260916/`
- 不含 `explicit_harm`：`reports/agentharm-p0p1-final-no-explicit-harm-20260916/`
- 每个目录均包含 JSON、CSV、Markdown 报告；DeepSeek 原始结构化响应缓存在本地 `deepseek-cache/`，不包含 API 密钥。
