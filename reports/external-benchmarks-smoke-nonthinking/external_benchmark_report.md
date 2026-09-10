# AI Aegis 外部 Agent 安全基准重放报告

> 口径：以下是离线 PreTool 网关重放，候选工具从未执行；检测率/阻断率不能与上游原生 ASR、Utility 或 Harm Score 直接比较。

## 运行元数据

```json
{
  "generated_at": "2026-09-09T15:14:57.851703+00:00",
  "aegis_commit": "9f27ae10d09f79ae745120dddce47f882833c251",
  "aegis_worktree_dirty": true,
  "implementation_sha256": "a705f7bcb2c48099995563927a353b94135499d04c65f0f232ee2a3d0dcf1604",
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
    "paid_api_calls_this_run": 6,
    "input_tokens": 3156,
    "output_tokens": 312,
    "failed_samples": 0,
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

样本：2（攻击 2，正常 0）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0015 |
| always_block | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 0.0003 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 3.2979 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 3.9987 |
| five_stage_semantic | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 0.2621 |
| deepseek_judge_live | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 904.6300 |
| five_stage_deepseek_live | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 904.8208 |

## agentharm_public

样本：2（攻击 2，正常 0）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0017 |
| always_block | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 0.0003 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 11.7389 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.9020 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.7403 |
| deepseek_judge_live | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 1013.8861 |
| five_stage_deepseek_live | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1014.5220 |

## agentdojo_catalog

样本：2（攻击 0，正常 2）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0011 |
| always_block | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0.0004 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.6130 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.3441 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.1086 |
| deepseek_judge_live | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 996.3227 |
| five_stage_deepseek_live | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 996.4248 |

## 解读边界

- `five_stage_rules` 只使用确定性规则和状态机。
- `five_stage_semantic` 仅对明确标注的间接注入使用上游标签作为语义信号，代表语义提取正确时的上界，不是假装调用了 DeepSeek。
- `deepseek_judge_live` 是 DeepSeek 直接输出 allow/confirm/block；`five_stage_deepseek_live` 复用同一次调用的离散证据，由确定性状态机裁决。
- 两个 live 方案复用每条样本的一次 API 响应，因此各表中的调用数与费用不可相加。失败请求按 confirm 记录，并单独报告失败数。
- `aegis_single_turn_local` 是 AI Aegis 本地单轮规则分析器，不包含会话状态。
- `always_allow` 与 `always_block` 用于暴露只追求可用性或只追求安全性的极端结果。
- 上游论文数字与来源见 `docs/BENCHMARK_RESEARCH.md`。
