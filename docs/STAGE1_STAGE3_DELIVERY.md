# 阶段一与阶段三交付记录

> 历史记录：本文保存 2026-09-08 首次离线回放结果。真实 DeepSeek 复测与最终交付口径以 `COMPETITION_ACCEPTANCE.md` 及对应机器 JSON 为准。

> 完成日期：2026-09-08
> 仓库 HEAD：`9f27ae10d09f79ae745120dddce47f882833c251`（被测实现含未提交工作区改动）
> 被测实现指纹：`3b8fa7de2d36fd305d3a7d14211a9095997560fad7b0f6e9c6a59752eed6d4ef`
> 口径：外部数据仅做离线 PreTool 网关回放，候选工具从未执行。

## 阶段一：P2 收口

完成项：

- Python 应用测试：834 通过、2 条件跳过、0 失败；43 项由测试配置预先排除。
- 插件与 UI Node 测试：211/211 通过。
- Windows 兼容：本地规则加载超时逻辑不再假设 `SIGALRM` 存在。
- 插件许可证：四个插件副本与根许可证逐字节一致。
- UI 合同：恢复 Blocked Ledger 独立页面，修复 Agent Map 动画类名与 Agent Runs 隐私标签。
- 无 DeepSeek API Key 启动：`/health` 正常。
- HTTP 冒烟：项目内 README 读取返回 `allow`、风险分数 0；`rm -rf /` 返回 `block`、风险分数 100、证据层为 Boundary。
- 补充回归用例，覆盖 JSON 工具参数包装不能绕过根目录递归删除检测。

两个跳过项分别是可选 Hermes 条件和 Windows 非管理员账户没有创建符号链接权限，不属于失败。

## 阶段三：公开 Benchmark 回放

接入三个官方公开数据源：

- InjecAgent：1,054 个攻击样本，并从官方用户任务生成 17 个正常控制，共 1,071 条。
- AgentHarm Public：176 个 harmful 与 176 个 benign，共 352 条。
- AgentDojo v1.2.2：官方四套件任务目录，97 个正常任务与 35 个注入任务，共 132 条；上游 commit 为 `089ed468cf3ed0322acc66b0211f26d9d90dbf60`。

总计 1,555 条 trace、5 种判定方案、7,775 次方案级回放。比较方案包括：`always_allow`、`always_block`、原始 `aegis_single_turn_local`、纯规则五段管线、带上游语义标签的五段管线上界。

真实 `deepseek_judge_live` 未运行，因为 1,423 个需语义判断的样本会产生付费 API 调用，本轮未取得费用授权；五段+免疫基线也未运行，因为必须先建立与测试集隔离的 train/shadow/test 分区，避免用测试真值训练抗体造成数据泄漏。二者均在机器报告中显式标为 `not_run`，没有用历史记录或模拟数据冒充实测。

核心结果：

| 数据集 | AI Aegis 单轮检出率/FPR | 五段纯规则检出率/FPR | 五段语义上界检出率/FPR |
|---|---:|---:|---:|
| InjecAgent | 4.84% / 0.00% | 0.00% / 0.00% | 100.00% / 0.00% |
| AgentHarm Public | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
| AgentDojo Catalog | 2.86% / 0.00% | 0.00% / 0.00% | 74.29% / 0.00% |

结果揭示的事实：

1. 原始单轮规则只能识别少量工具参数中直接出现的危险特征。
2. InjecAgent 的恶意主要存在于不可信工具返回的语义中，候选工具调用本身可以完全合法；因此纯 PreTool 参数规则为 0%，而正确语义证据进入 Drift/Friction 后可阻断全部标注攻击。这里的 100% 是“语义提取正确时的上界”，不是 DeepSeek 实测。
3. AgentHarm 的攻击标签来自用户有害目标。本轮适配器只回放目标工具序列，没有把用户目标伪装成工具参数，因此所有 PreTool 方案均为 0%。这不是好成绩，而是证明下一阶段必须把 `llm_input/user_intent` 意图流接入同一评测合同。
4. `always_block` 虽然攻击检出为 100%，但正常误报也为 100%，说明不能用全拒绝制造安全成绩。

## 与论文数字的关系

上游数字只作背景参考，不能放进同一排行榜：

- InjecAgent 论文报告其 GPT-4 ReAct 基础攻击成功率约 24%，增强攻击约 47%。这是攻击成功率，不是本项目的网关检出率。
- AgentDojo 官方历史配置报告 no-defense ASR 47.69%、tool-filter ASR 6.84%。这是完整 Agent harness 的攻击成功率，也不是静态工具回放检出率。
- AgentHarm 使用 Harm Score、Refusal 等完整 Agent 指标，本轮公开子集的工具序列回放不能直接对齐。

要形成可公开宣称的同口径横向比较，下一次应固定同一 victim model、同一任务和随机设置，把 AI Aegis 嵌入 AgentDojo 原生 harness，同时报告 ASR 与 Utility 的变化。

## 复现

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
D:\pyt\python.exe scripts/run_external_benchmarks.py `
  --benchmarks injecagent agentharm agentdojo `
  --agentdojo-root C:\path\to\agentdojo `
  --agentdojo-deps C:\path\to\isolated-dependencies `
  --output-dir reports\external-benchmarks
```

具体来源、许可证和论文口径见 `docs/BENCHMARK_RESEARCH.md`；逐项指标见 `reports/external-benchmarks/` 下的 Markdown、JSON 和 CSV。
