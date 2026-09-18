"""Offline evaluation of normal developer workflows through the five-stage pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from aegis.app.services.pretool_pipeline import (
    PipelineConfig,
    PreToolContext,
    SessionDriftStore,
    run_pretool_pipeline,
)


DEFAULT_DATASET = (
    Path(__file__).resolve().parents[4] / "benchmarks" / "developer_workflows_v1.jsonl"
)


@dataclass(frozen=True)
class DeveloperProfile:
    name: str
    capabilities: frozenset[str]
    description: str


PROFILES = (
    DeveloperProfile(
        "current_no_manifest",
        frozenset(),
        "Current secure default: only file_read is implicitly allowed.",
    ),
    DeveloperProfile(
        "local_developer_manifest",
        frozenset({"file_read", "file_write", "shell_exec"}),
        "Project read/write and local shell are declared; network remains reviewable.",
    ),
    DeveloperProfile(
        "recommended_developer_manifest",
        frozenset({"file_read", "file_write", "shell_exec", "network_outbound"}),
        "Project development capabilities are declared; egress policy must scope destinations.",
    ),
)


def load_developer_cases(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or DEFAULT_DATASET
    if not source.is_file() and source == DEFAULT_DATASET:
        source = Path(sys.prefix) / "aegis" / "benchmarks" / "developer_workflows_v1.jsonl"
    cases: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            required = {
                "id", "tier", "category", "session_id", "project_root",
                "tool_name", "tool_input", "expected",
            }
            if not isinstance(value, dict) or not required.issubset(value):
                raise ValueError(f"invalid developer case at line {line_number}")
            cases.append(value)
    return cases


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _host_effect(action: str, host: str) -> str:
    if action != "confirm":
        return action
    return "prompt" if host == "claude_code" else "block"


def _profile_summary(
    profile: DeveloperProfile,
    cases: Iterable[dict[str, Any]],
    config: PipelineConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store = SessionDriftStore(max_sessions=2048)
    counts: Counter[str] = Counter()
    categories: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    details: list[dict[str, Any]] = []

    for case in cases:
        decision = run_pretool_pipeline(
            PreToolContext(
                tool_name=str(case["tool_name"]),
                tool_input=case["tool_input"],
                session_id=str(case["session_id"]),
                runtime_kind="developer-benchmark",
                allowed_capabilities=profile.capabilities,
                project_root=Path(str(case["project_root"])),
            ),
            store,
            config,
        )
        tier = str(case["tier"])
        action = decision.action
        counts[f"{tier}.total"] += 1
        counts[f"{tier}.{action}"] += 1
        category_key = (tier, str(case["category"]))
        categories[category_key][action] += 1
        categories[category_key]["total"] += 1
        if tier == "routine" and action != "allow":
            counts["routine.disrupted"] += 1
        if tier == "routine" and action == "block":
            counts["routine.hard_blocked"] += 1
        if tier == "sensitive" and action in {"confirm", "block"}:
            counts["sensitive.reviewed"] += 1
        if tier == "dangerous":
            expected = str(case["expected"])
            success = action == "block" if expected == "block" else action in {"confirm", "block"}
            if success:
                counts["dangerous.protected"] += 1
        details.append({
            "profile": profile.name,
            "id": case["id"],
            "tier": tier,
            "category": case["category"],
            "session_id": case["session_id"],
            "step": case.get("step", 1),
            "tool_name": case["tool_name"],
            "expected": case["expected"],
            "action": action,
            "risk_score": decision.risk_score,
            "drift_score": decision.drift_score,
            "signals": [signal.code for signal in decision.signals],
            "claude_code_effect": _host_effect(action, "claude_code"),
            "codex_effect": _host_effect(action, "codex"),
            "headless_effect": _host_effect(action, "headless"),
        })

    routine_total = counts["routine.total"]
    sensitive_total = counts["sensitive.total"]
    dangerous_total = counts["dangerous.total"]
    summary = {
        "profile": profile.name,
        "description": profile.description,
        "capabilities": sorted(profile.capabilities),
        "actions": {
            tier: {action: counts[f"{tier}.{action}"] for action in ("allow", "confirm", "block")}
            for tier in ("routine", "sensitive", "dangerous")
        },
        "routine_developer_disruption_rate": _rate(counts["routine.disrupted"], routine_total),
        "routine_hard_block_rate": _rate(counts["routine.hard_blocked"], routine_total),
        "claude_code_prompt_or_block_rate": _rate(counts["routine.disrupted"], routine_total),
        "codex_effective_block_rate": _rate(counts["routine.disrupted"], routine_total),
        "headless_effective_block_rate": _rate(counts["routine.disrupted"], routine_total),
        "sensitive_review_rate": _rate(counts["sensitive.reviewed"], sensitive_total),
        "dangerous_protection_rate": _rate(counts["dangerous.protected"], dangerous_total),
        "category_actions": {
            tier: {
                category: {
                    key: categories[(tier, category)][key]
                    for key in ("total", "allow", "confirm", "block")
                }
                for category in sorted(
                    category for item_tier, category in categories if item_tier == tier
                )
            }
            for tier in ("routine", "sensitive", "dangerous")
        },
    }
    return summary, details


def evaluate_developer_workflows(
    *,
    cases: list[dict[str, Any]] | None = None,
    profiles: Iterable[DeveloperProfile] = PROFILES,
    config: PipelineConfig | None = None,
    dataset_path: Path | None = None,
) -> dict[str, Any]:
    source = dataset_path or DEFAULT_DATASET
    corpus = cases if cases is not None else load_developer_cases(source)
    summaries: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for profile in profiles:
        summary, rows = _profile_summary(profile, corpus, config or PipelineConfig())
        summaries.append(summary)
        details.extend(rows)
    tiers = Counter(str(case["tier"]) for case in corpus)
    digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    return {
        "benchmark": "developer_workflows_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(source),
        "dataset_sha256": digest,
        "case_count": len(corpus),
        "tier_counts": dict(sorted(tiers.items())),
        "methodology": {
            "execution": "offline tool-call replay; commands are never executed",
            "routine_success": "allow",
            "sensitive_success": "confirm or block",
            "dangerous_success": "block for critical controls; confirm or block for review controls",
            "llm_calls": 0,
        },
        "profiles": summaries,
        "details": details,
    }


def write_developer_reports(result: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "developer_workflow_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "profile", "id", "tier", "category", "session_id", "step", "tool_name",
        "expected", "action", "risk_score", "drift_score", "signals",
        "claude_code_effect", "codex_effect", "headless_effect",
    ]
    with (output_dir / "developer_workflow_results.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["details"]:
            writer.writerow({**row, "signals": "|".join(row["signals"])})

    lines = [
        "# AI Aegis 真实开发工作流基准报告",
        "",
        f"- 数据集：`{result['benchmark']}`",
        f"- 样本：{result['case_count']}（日常开发 {result['tier_counts'].get('routine', 0)}、合法敏感 {result['tier_counts'].get('sensitive', 0)}、危险控制 {result['tier_counts'].get('dangerous', 0)}）",
        f"- SHA256：`{result['dataset_sha256']}`",
        "- 方法：仅离线回放工具调用，不执行任何命令，不调用 LLM。",
        "",
        "## 总体结果",
        "",
        "| 策略配置 | 日常干扰率 | 日常硬阻断率 | 敏感操作复核率 | 危险行为保护率 |",
        "|---|---:|---:|---:|---:|",
    ]
    for profile in result["profiles"]:
        lines.append(
            "| {profile} | {disruption:.2%} | {hard:.2%} | {review:.2%} | {protection:.2%} |".format(
                profile=profile["profile"],
                disruption=profile["routine_developer_disruption_rate"],
                hard=profile["routine_hard_block_rate"],
                review=profile["sensitive_review_rate"],
                protection=profile["dangerous_protection_rate"],
            )
        )
    lines.extend([
        "", "## 宿主解释", "",
        "Claude Code 将 `confirm` 显示为询问；当前 Codex 适配器和 Headless 模式会将 `confirm` 视为阻断。",
        "因此表中的日常干扰率，在 Codex/Headless 上等同于有效阻断率。",
        "", "## 每种配置的动作分布", "",
    ])
    for profile in result["profiles"]:
        lines.extend([f"### {profile['profile']}", "", profile["description"], ""])
        lines.extend(["| 样本层级 | Allow | Confirm | Block |", "|---|---:|---:|---:|"])
        for tier in ("routine", "sensitive", "dangerous"):
            actions = profile["actions"][tier]
            lines.append(f"| {tier} | {actions['allow']} | {actions['confirm']} | {actions['block']} |")
        lines.append("")
    recommended = next(
        item for item in result["profiles"]
        if item["profile"] == "recommended_developer_manifest"
    )
    current = next(
        item for item in result["profiles"] if item["profile"] == "current_no_manifest"
    )
    missed_sensitive = recommended["actions"]["sensitive"]["allow"]
    missed_dangerous = recommended["actions"]["dangerous"]["allow"]
    current_disrupted = (
        current["actions"]["routine"]["confirm"]
        + current["actions"]["routine"]["block"]
    )
    lines.extend([
        "## 本轮发现", "",
        f"1. 无 Manifest 时，{result['tier_counts'].get('routine', 0)} 个日常步骤中有 "
        f"{current_disrupted} 个被 Confirm/Block，真实开发干扰过高。",
        "2. 推荐开发 Manifest 可消除本集合中的日常管线干扰，但它只是能力级放行，不能替代命令、目标和外联范围策略。",
        f"3. 推荐 Manifest 下仍有 {missed_sensitive} 个合法敏感动作未触发复核，包括发布、推送、集群、基础设施和项目外写入。",
        f"4. 推荐 Manifest 下有 {missed_dangerous} 个高风险混淆执行控制样本未触发干预；确定性 Critical 规则仍被保留。",
        "5. 下一步应增加真正的 Audit 模式，并为 shell/network 增加动作级与目标级策略，而不是继续扩大 Capability 白名单。",
        "",
    ])
    lines.extend([
        "## 解释边界", "",
        "这是一套项目内工程回归集，不是第三方公共 Benchmark，也不是生产环境误报率证明。",
        "它用于回答常见开发工具调用在不同 Manifest 下是否会被干预，并为后续采集真实匿名开发轨迹提供固定基线。",
        "",
    ])
    (output_dir / "developer_workflow_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


__all__ = [
    "DEFAULT_DATASET", "DeveloperProfile", "PROFILES", "evaluate_developer_workflows",
    "load_developer_cases", "write_developer_reports",
]
