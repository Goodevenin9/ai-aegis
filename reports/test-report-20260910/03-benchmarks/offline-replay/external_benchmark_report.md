# AI Aegis 外部 Agent 安全基准重放报告

> 口径：以下是离线 PreTool 网关重放，候选工具从未执行；检测率/阻断率不能与上游原生 ASR、Utility 或 Harm Score 直接比较。

## 运行元数据

```json
{
  "generated_at": "2026-09-10T14:55:15.903153+00:00",
  "aegis_commit": "4acffee7cd9ce74171cd6f51861b7328128bd42c",
  "aegis_worktree_dirty": true,
  "implementation_sha256": "070eefa569911125f1e4eabb56bda226664c3a2738f0f6ba080a8ebe42df830c",
  "agentdojo_commit": null,
  "python": "3.14.0",
  "platform": "Windows-11-10.0.26200-SP0",
  "pipeline_config_sha256": "73ce1b2544958b81e85a7b265655da7fe51d0a1a9cfedab681833e0ad9b7bf6d",
  "network_sources": "official repositories/dataset cards listed in docs/BENCHMARK_RESEARCH.md",
  "tool_execution": "disabled",
  "baseline_status": {
    "deepseek_judge_live": "not_run_no_paid_api_authorization",
    "five_stage_immunity": "not_run_requires_leakage_safe_train_shadow_test_split"
  },
  "deepseek": {
    "model": null,
    "evidence_schema_version": null,
    "paid_api_calls_for_result_set": 0,
    "new_paid_api_calls_during_this_invocation": 0,
    "api_responses_represented": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "failed_samples": 0,
    "estimated_cost_usd": 0.0,
    "responses_reused_between_live_variants": true,
    "pricing_assumption_usd_per_million": null
  }
}
```

## 未运行基线

- `deepseek_judge_live`: `not_run_no_paid_api_authorization`
- `five_stage_immunity`: `not_run_requires_leakage_safe_train_shadow_test_split`

## injecagent

样本：1071（攻击 1054，正常 17）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0002 |
| always_block | 100.00% | 100.00% | 100.00% | 98.41% | 99.20% | 0.0002 |
| aegis_single_turn_local | 4.84% | 4.84% | 0.00% | 100.00% | 9.23% | 8.1443 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.4315 |
| five_stage_semantic | 100.00% | 100.00% | 0.00% | 100.00% | 100.00% | 0.4307 |

## agentharm_public

样本：352（攻击 176，正常 176）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0001 |
| always_block | 100.00% | 100.00% | 100.00% | 50.00% | 66.67% | 0.0002 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 21.2541 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.5461 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.5797 |

## 解读边界

- `five_stage_rules` 只使用确定性规则和状态机。
- `five_stage_semantic` 仅对明确标注的间接注入使用上游标签作为语义信号，代表语义提取正确时的上界，不是假装调用了 DeepSeek。
- `deepseek_judge_live` 是 DeepSeek 直接输出 allow/confirm/block；`five_stage_deepseek_live` 复用同一次调用的离散证据，由确定性状态机裁决。
- 两个 live 方案复用每条样本的一次 API 响应，因此各表中的调用数与费用不可相加。失败请求按 confirm 记录，并单独报告失败数。
- `aegis_single_turn_local` 是 AI Aegis 本地单轮规则分析器，不包含会话状态。
- `always_allow` 与 `always_block` 用于暴露只追求可用性或只追求安全性的极端结果。
- 上游论文数字与来源见 `docs/BENCHMARK_RESEARCH.md`。
