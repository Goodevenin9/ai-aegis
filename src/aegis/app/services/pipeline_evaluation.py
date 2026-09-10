"""Deterministic offline A/B evaluation for the P1 Chinese Agent corpus."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from aegis.app.services.pretool_pipeline import (
    IntentEvidence,
    PipelineConfig,
    PreToolContext,
    SemanticLabels,
    SessionDriftStore,
    run_pretool_pipeline,
)

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[4] / "benchmarks" / "chinese_agent_security_p1.jsonl"
)
VARIANTS = frozenset({"aegis_single_turn", "deepseek_judge_recorded", "five_stage"})


def _installed_dataset() -> Path:
    return Path(sys.prefix) / "aegis" / "benchmarks" / "chinese_agent_security_p1.jsonl"


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or DEFAULT_DATASET
    if not path.is_file() and path == DEFAULT_DATASET:
        path = _installed_dataset()
    cases = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or "malicious" not in value:
                raise ValueError(f"invalid evaluation case at line {line_number}")
            cases.append(value)
    return cases


def _semantic_evidence(case: dict[str, Any]) -> IntentEvidence:
    raw = case.get("semantic") or {}
    return IntentEvidence(
        labels=SemanticLabels(
            theme_shifted=bool(raw.get("theme_shifted", False)),
            permission_probing=bool(raw.get("permission_probing", False)),
            request_escalation=bool(raw.get("request_escalation", False)),
        ),
        requested_capabilities=frozenset(case.get("requested_capabilities") or []),
        requested_radius=case.get("requested_radius", "none"),
    )


def _five_stage_action(
    case: dict[str, Any],
    store: SessionDriftStore,
    config: PipelineConfig,
) -> str:
    session_id = str(case["session_id"])
    state = store.get(session_id)
    if state.original_intent is None:
        store.observe_intent(session_id, str(case.get("text") or ""))
    elif case.get("text"):
        store.observe_intent(session_id, str(case["text"]))
    evidence = _semantic_evidence(case)
    if evidence != IntentEvidence():
        store.observe_intent_evidence(session_id, evidence)
    return run_pretool_pipeline(
        PreToolContext(
            tool_name=str(case["tool_name"]),
            tool_input=case.get("tool_input") or {},
            session_id=session_id,
            runtime_kind="evaluation",
            base_decision=case.get("base_decision", "allow"),
            allowed_capabilities=frozenset(case.get("capabilities") or []),
            project_root=Path(case["project_root"]) if case.get("project_root") else None,
        ),
        store,
        config,
    ).action


def evaluate_variants(
    variants: Iterable[str],
    *,
    cases: list[dict[str, Any]] | None = None,
    config: PipelineConfig | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    selected = list(dict.fromkeys(variants))
    unknown = set(selected) - VARIANTS
    if unknown:
        raise ValueError(f"unknown variants: {', '.join(sorted(unknown))}")
    corpus = cases if cases is not None else load_cases()
    results = []
    for variant in selected:
        store = SessionDriftStore(max_sessions=max(1, len(corpus)))
        counts = Counter()
        details = []
        for case in corpus:
            if variant == "aegis_single_turn":
                action = {"allow": "allow", "ask": "confirm", "deny": "block"}[
                    case.get("base_decision", "allow")
                ]
            elif variant == "deepseek_judge_recorded":
                action = case.get("judge_action", "allow")
            else:
                action = _five_stage_action(case, store, config or PipelineConfig())
            malicious = bool(case["malicious"])
            detected = action in {"confirm", "block"}
            counts[action] += 1
            counts["tp" if malicious and detected else
                   "fn" if malicious else
                   "fp" if detected else "tn"] += 1
            if include_details:
                details.append(
                    {"id": case["id"], "malicious": malicious, "action": action}
                )
        positives = counts["tp"] + counts["fn"]
        negatives = counts["tn"] + counts["fp"]
        total = max(1, len(corpus))
        item = {
            "variant": variant,
            "cases": len(corpus),
            "actions": {key: counts[key] for key in ("allow", "confirm", "block")},
            "confusion": {key: counts[key] for key in ("tp", "fp", "tn", "fn")},
            "attack_recall": round(counts["tp"] / positives, 4) if positives else 0.0,
            "benign_false_positive_rate": round(counts["fp"] / negatives, 4) if negatives else 0.0,
            "accuracy": round((counts["tp"] + counts["tn"]) / total, 4),
        }
        if include_details:
            item["details"] = details
        results.append(item)
    return {
        "dataset": "chinese_agent_security_p1",
        "case_count": len(corpus),
        "judge_note": (
            "deepseek_judge_recorded uses dataset-recorded judge outcomes; "
            "it does not call an external API during replay"
        ),
        "results": results,
    }


__all__ = ["DEFAULT_DATASET", "VARIANTS", "evaluate_variants", "load_cases"]
