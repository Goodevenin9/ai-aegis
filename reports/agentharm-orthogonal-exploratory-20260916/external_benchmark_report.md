# AI Aegis 外部 Agent 安全基准重放报告

> 口径：以下是离线 PreTool 网关重放，候选工具从未执行；检测率/阻断率不能与上游原生 ASR、Utility 或 Harm Score 直接比较。

## 运行元数据

```json
{
  "generated_at": "2026-09-16T07:31:04.846478+00:00",
  "aegis_commit": "f3a54380f540d718734b285c942a8ca2d412c85e",
  "aegis_worktree_dirty": true,
  "implementation_sha256": "80277ad7bcf85d800f64dd8f428cf15b0a9c9188de29da93ff511226128009d4",
  "agentdojo_commit": null,
  "python": "3.14.0",
  "platform": "Windows-11-10.0.26200-SP0",
  "pipeline_config_sha256": "5c5f34d0c11a65e1c256cdc2e80a1a402197b527f31ecc1606c5f765d2c8fdea",
  "network_sources": "official repositories/dataset cards listed in docs/BENCHMARK_RESEARCH.md",
  "tool_execution": "disabled",
  "baseline_status": {
    "deepseek_judge_live": "completed",
    "five_stage_immunity": "not_run_requires_leakage_safe_train_shadow_test_split"
  },
  "deepseek": {
    "model": "deepseek-v4-flash",
    "evidence_schema_version": "v4-orthogonal-explicit-harm",
    "includes_explicit_harm": true,
    "paid_api_calls_for_result_set": 352,
    "new_paid_api_calls_during_this_invocation": 0,
    "api_responses_represented": 352,
    "input_tokens": 350755,
    "output_tokens": 31208,
    "failed_samples": 0,
    "estimated_cost_usd": 0.057844,
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

## agentharm_public

样本：352（攻击 176，正常 176）

| 方案 | 攻击检出率 | 硬阻断率 | 正常误报率 | 正常确认率 | 正常硬阻断率 | Precision | F1 | P95延迟(ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| always_allow | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.0002 |
| always_block | 100.00% | 100.00% | 100.00% | 0.00% | 100.00% | 50.00% | 66.67% | 0.0001 |
| aegis_single_turn_local | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 15.1467 |
| five_stage_rules | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.0808 |
| five_stage_semantic | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 1.0636 |
| deepseek_judge_live | 89.20% | 89.20% | 19.89% | 3.98% | 15.91% | 81.77% | 85.33% | 1083.5273 |
| five_stage_deepseek_live | 51.14% | 22.16% | 6.25% | 4.55% | 1.70% | 89.11% | 64.98% | 1083.8365 |

### 误报归因

- `always_block` 误报归因：`decision.block`=176
- `deepseek_judge_live` 误报归因：`decision.confirm`=7、`decision.block`=28
- `five_stage_deepseek_live` 误报归因：`decision.confirm`=8、`semantic.explicit_harm`=11、`decision.block`=3、`semantic.permission_probing`=2、`semantic.request_escalation`=3

## 解读边界

- `five_stage_rules` 只使用确定性规则和状态机。
- `five_stage_semantic` 仅对明确标注的间接注入使用上游标签作为语义信号，代表语义提取正确时的上界，不是假装调用了 DeepSeek。
- `deepseek_judge_live` 是 DeepSeek 直接输出 allow/confirm/block；`five_stage_deepseek_live` 复用同一次调用的离散证据，由确定性状态机裁决。
- 两个 live 方案复用每条样本的一次 API 响应，因此各表中的调用数与费用不可相加。失败请求按 confirm 记录，并单独报告失败数。
- `aegis_single_turn_local` 是 AI Aegis 本地单轮规则分析器，不包含会话状态。
- `always_allow` 与 `always_block` 用于暴露只追求可用性或只追求安全性的极端结果。
- 上游论文数字与来源见 `docs/BENCHMARK_RESEARCH.md`。
