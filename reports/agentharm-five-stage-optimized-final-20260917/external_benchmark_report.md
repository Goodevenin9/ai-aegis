# AI Aegis 外部 Agent 安全基准重放报告

> 口径：以下是离线 PreTool 网关重放，候选工具从未执行；检测率/阻断率不能与上游原生 ASR、Utility 或 Harm Score 直接比较。

## 运行元数据

```json
{
  "generated_at": "2026-09-17T05:40:58.943739+00:00",
  "aegis_commit": "ff6969c6fa3476c4e980a72c15d4c6e6d4cd81ce",
  "aegis_worktree_dirty": true,
  "implementation_sha256": "385e0c927a56381b27a1d2bcdf9dc9c9d9c5ef06cd3f8124813c1f6c942e825b",
  "agentdojo_commit": null,
  "python": "3.11.15",
  "platform": "Windows-10-10.0.26200-SP0",
  "pipeline_config_sha256": "3b1adba1d396b4a5fa653c23c6c3cf9c242aebc0b7ed1a1b1d359798d2476e08",
  "network_sources": "official repositories/dataset cards listed in docs/BENCHMARK_RESEARCH.md",
  "tool_execution": "disabled",
  "calibration_status": "Pipeline defaults were selected using this same public AgentHarm split; results are in-sample post-calibration, not an independent generalization estimate.",
  "baseline_status": {
    "deepseek_judge_live": "completed",
    "five_stage_immunity": "not_run_requires_leakage_safe_train_shadow_test_split"
  },
  "deepseek": {
    "model": "deepseek-v4-flash",
    "evidence_schema_version": "v4-orthogonal-explicit-harm",
    "includes_explicit_harm": true,
    "paid_api_calls_for_result_set": 352,
    "new_paid_api_calls_during_this_invocation": 8,
    "api_responses_represented": 352,
    "focused_verifier_enabled": true,
    "focused_verifier_candidates": 8,
    "focused_verifier_responses": 8,
    "input_tokens": 354810,
    "output_tokens": 31270,
    "failed_samples": 0,
    "estimated_cost_usd": 0.058429,
    "responses_reused_between_live_variants": true,
    "pricing_assumption_usd_per_million": {
      "input_cache_miss": 0.14,
      "output": 0.28
    }
  }
}
```

## 校准与泛化边界

> Pipeline defaults were selected using this same public AgentHarm split; results are in-sample post-calibration, not an independent generalization estimate.

## 未运行基线

- `deepseek_judge_live`: `completed`
- `five_stage_immunity`: `not_run_requires_leakage_safe_train_shadow_test_split`

## agentharm_public

样本：352（攻击 176，正常 176）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | 正常确认率 | 正常硬阻断率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0002 |
| always_block | 100.00% | 100.00% | 100.00% | 0.00% | 100.00% | 50.00% | 66.67% | 0.0002 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 24.5029 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.5900 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.7385 |
| deepseek_judge_live | 89.20% | 89.20% | 17.05% | 0.57% | 16.48% | 83.96% | 86.50% | 1133.9052 |
| five_stage_deepseek_live | 89.20% | 80.11% | 16.48% | 0.00% | 16.48% | 84.41% | 86.74% | 1135.6709 |
| five_stage_deepseek_verified_live | 90.34% | 81.25% | 16.48% | 0.00% | 16.48% | 84.57% | 87.36% | 1251.9030 |

### 误报正权重证据共现

- `always_block` 误报正权重证据共现：`decision.block`=176
- `deepseek_judge_live` 误报正权重证据共现：`decision.block`=29、`decision.confirm`=1
- `five_stage_deepseek_live` 误报正权重证据共现：`decision.block`=29、`semantic.explicit_harm`=29、`semantic.irreversible_impact`=18、`semantic.permission_probing`=3、`semantic.request_escalation`=6
- `five_stage_deepseek_verified_live` 误报正权重证据共现：`decision.block`=29、`semantic.explicit_harm`=29、`semantic.irreversible_impact`=18、`semantic.permission_probing`=3、`semantic.request_escalation`=6

## 解读边界

- `five_stage_rules` 只使用确定性规则和状态机。
- `five_stage_semantic` 仅对明确标注的间接注入使用上游标签作为语义信号，代表语义提取正确时的上界，不是假装调用了 DeepSeek。
- `deepseek_judge_live` 是 DeepSeek 直接输出 allow/confirm/block；`five_stage_deepseek_live` 复用同一次调用的离散证据，由确定性状态机裁决。
- 两个 live 方案复用每条样本的一次 API 响应，因此各表中的调用数与费用不可相加。失败请求按 confirm 记录，并单独报告失败数。
- `aegis_single_turn_local` 是 AI Aegis 本地单轮规则分析器，不包含会话状态。
- `always_allow` 与 `always_block` 用于暴露只追求可用性或只追求安全性的极端结果。
- 上游论文数字与来源见 `docs/BENCHMARK_RESEARCH.md`。
