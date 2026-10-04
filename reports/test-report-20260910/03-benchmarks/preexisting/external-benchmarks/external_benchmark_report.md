# AI Aegis 外部 Agent 安全基准重放报告

> 口径：以下是离线 PreTool 网关重放，候选工具从未执行；检测率/阻断率不能与上游原生 ASR、Utility 或 Harm Score 直接比较。

## 运行元数据

```json
{
  "generated_at": "2026-09-09T15:27:43.576520+00:00",
  "aegis_commit": "9f27ae10d09f79ae745120dddce47f882833c251",
  "aegis_worktree_dirty": true,
  "implementation_sha256": "e289fc9f0dc7b13af5b0d354e321f6ade37105c21f1019692873a774e771e5c1",
  "agentdojo_commit": "089ed468cf3ed0322acc66b0211f26d9d90dbf60",
  "python": "3.14.0",
  "platform": "Windows-11-10.0.26200-SP0",
  "pipeline_config_sha256": "080269d981facae3a0554f4215d20189f64988b5bfc53ceb900bc2d420f83964",
  "network_sources": "official repositories/dataset cards listed in docs/BENCHMARK_RESEARCH.md",
  "tool_execution": "disabled",
  "baseline_status": {
    "deepseek_judge_live": "completed",
    "five_stage_immunity": "not_run_requires_leakage_safe_train_shadow_test_split"
  },
  "deepseek": {
    "model": "deepseek-v4-flash",
    "paid_api_calls_for_result_set": 1555,
    "new_paid_api_calls_during_this_invocation": 0,
    "api_responses_represented": 1555,
    "input_tokens": 867908,
    "output_tokens": 83387,
    "failed_samples": 0,
    "estimated_cost_usd": 0.144855,
    "responses_reused_between_live_variants": true,
    "pricing_assumption_usd_per_million": {
      "input_cache_miss": 0.14,
      "output": 0.28
    }
  }
}
```

## 未运行基线

- `deepseek_judge_live`: `completed`
- `five_stage_immunity`: `not_run_requires_leakage_safe_train_shadow_test_split`

## injecagent

样本：1071（攻击 1054，正常 17）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0001 |
| always_block | 100.00% | 100.00% | 100.00% | 98.41% | 99.20% | 0.0001 |
| aegis_single_turn_local | 4.84% | 4.84% | 0.00% | 100.00% | 9.23% | 6.3683 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.3844 |
| five_stage_semantic | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 0.3569 |
| deepseek_judge_live | 100.00% | 99.72% | 0.00% | 100.00% | 100.00% | N/A |
| five_stage_deepseek_live | 100.00% | 98.20% | 0.00% | 100.00% | 100.00% | N/A |

## agentharm_public

样本：352（攻击 176，正常 176）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0001 |
| always_block | 100.00% | 100.00% | 100.00% | 50.00% | 66.67% | 0.0001 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 15.4329 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.0405 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.9891 |
| deepseek_judge_live | 90.34% | 89.20% | 22.73% | 79.90% | 84.80% | N/A |
| five_stage_deepseek_live | 37.50% | 0.00% | 19.89% | 65.35% | 47.65% | N/A |

## agentdojo_catalog

样本：132（攻击 35，正常 97）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0001 |
| always_block | 100.00% | 100.00% | 100.00% | 26.52% | 41.92% | 0.0001 |
| aegis_single_turn_local | 2.86% | 2.86% | 0.00% | 100.00% | 5.56% | 14.1604 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.7713 |
| five_stage_semantic | 74.29% | 74.29% | 0.00% | 100.00% | 85.25% | 0.7318 |
| deepseek_judge_live | 62.86% | 60.00% | 13.40% | 62.86% | 62.86% | N/A |
| five_stage_deepseek_live | 42.86% | 20.00% | 14.43% | 51.72% | 46.88% | N/A |

## 解读边界

- `five_stage_rules` 只使用确定性规则和状态机。
- `five_stage_semantic` 仅对明确标注的间接注入使用上游标签作为语义信号，代表语义提取正确时的上界，不是假装调用了 DeepSeek。
- `deepseek_judge_live` 是 DeepSeek 直接输出 allow/confirm/block；`five_stage_deepseek_live` 复用同一次调用的离散证据，由确定性状态机裁决。
- 两个 live 方案复用每条样本的一次 API 响应，因此各表中的调用数与费用不可相加。失败请求按 confirm 记录，并单独报告失败数。
- `aegis_single_turn_local` 是 AI Aegis 本地单轮规则分析器，不包含会话状态。
- `always_allow` 与 `always_block` 用于暴露只追求可用性或只追求安全性的极端结果。
- 上游论文数字与来源见 `docs/BENCHMARK_RESEARCH.md`。
