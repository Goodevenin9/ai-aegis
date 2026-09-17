"""Run side-effect-free third-party Agent-security benchmark replays."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from aegis.app.services.external_benchmark_evaluation import (  # noqa: E402
    DeepSeekBenchmarkEvaluator,
    LIVE_REPLAY_VARIANTS,
    LiveSemanticDecision,
    REPLAY_VARIANTS,
    evaluate_replay,
    load_agentdojo,
    load_agentharm,
    load_injecagent,
    live_semantic_decision_from_json,
    live_semantic_decision_to_json,
    write_replay_reports,
    _fetch_text,
)
from aegis.app.services.pretool_pipeline import PipelineConfig  # noqa: E402


def _commit(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _is_dirty(path: Path) -> bool | None:
    try:
        return bool(subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True,
            stderr=subprocess.DEVNULL, timeout=10,
        ).strip())
    except (OSError, subprocess.SubprocessError):
        return None


def _implementation_sha256() -> str:
    """Fingerprint the exact security/evaluation source used by this run."""

    digest = hashlib.sha256()
    for relative in (
        "scripts/run_external_benchmarks.py",
        "src/aegis/app/services/chinese_security_rules.py",
        "src/aegis/app/services/external_benchmark_evaluation.py",
        "src/aegis/app/services/pretool_pipeline.py",
        "src/aegis/utils/security.py",
    ):
        path = REPO_ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_counts(corpus: object) -> None:
    expected = {
        "injecagent": (1071, 1054, 17),
        "agentharm_public": (352, 176, 176),
        "agentdojo_catalog": (132, 35, 97),
    }
    name = getattr(corpus, "name")
    traces = getattr(corpus, "traces")
    actual = (len(traces), sum(trace.malicious for trace in traces), sum(not trace.malicious for trace in traces))
    if actual != expected[name]:
        raise RuntimeError(f"{name} source count changed: expected {expected[name]}, got {actual}")


def _source_fetcher(cache_dir: Path):
    """Return a retrying, content-addressed source loader for reproducible reruns."""

    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(url: str) -> str:
        cache_path = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.txt"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                content = _fetch_text(url)
                cache_path.write_text(content, encoding="utf-8")
                return content
            except Exception as exc:  # the fixed URL/hash is recorded in the report
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (2**attempt))
        raise RuntimeError(f"benchmark source unavailable after retries: {url}") from last_error

    return fetch


def _load_live_cache(path: Path) -> dict[str, LiveSemanticDecision]:
    results: dict[str, LiveSemanticDecision] = {}
    if not path.exists():
        return results
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        value = live_semantic_decision_from_json(row)
        if value.status == "ok":
            results[str(row["case_id"])] = value
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay public Agent-security datasets through AI Aegis without executing tools."
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=REPO_ROOT / "reports" / "external-benchmarks",
    )
    parser.add_argument("--agentdojo-root", type=Path)
    parser.add_argument("--agentdojo-deps", type=Path)
    parser.add_argument(
        "--benchmarks", nargs="+", choices=("injecagent", "agentharm", "agentdojo"),
        default=("injecagent", "agentharm"),
    )
    parser.add_argument("--live-deepseek", action="store_true")
    parser.add_argument("--deepseek-api-key-file", type=Path)
    parser.add_argument("--deepseek-model", default="deepseek-v4-flash")
    parser.add_argument("--deepseek-concurrency", type=int, default=12)
    parser.add_argument(
        "--evidence-schema", choices=("legacy", "explicit-harm"),
        default="explicit-harm",
        help="DeepSeek evidence contract; legacy omits the explicit_harm label",
    )
    parser.add_argument("--limit", type=int, help="Per-benchmark smoke-test limit")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    fetch_source = _source_fetcher(args.output_dir / "source-cache")

    corpora = []
    if "injecagent" in args.benchmarks:
        corpora.append(load_injecagent(fetch_text=fetch_source))
    if "agentharm" in args.benchmarks:
        corpora.append(load_agentharm(fetch_text=fetch_source))
    if "agentdojo" in args.benchmarks:
        if not args.agentdojo_root:
            parser.error("--agentdojo-root is required when agentdojo is selected")
        corpora.append(
            load_agentdojo(args.agentdojo_root, dependency_root=args.agentdojo_deps)
        )

    reports = []
    total_paid_calls = 0
    total_represented_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_failures = 0
    evaluator = None
    if args.live_deepseek:
        if not args.deepseek_api_key_file:
            parser.error("--deepseek-api-key-file is required with --live-deepseek")
        api_key = args.deepseek_api_key_file.read_text(encoding="utf-8-sig").strip()
        evaluator = DeepSeekBenchmarkEvaluator(
            api_key,
            model=args.deepseek_model,
            concurrency=args.deepseek_concurrency,
            include_explicit_harm=args.evidence_schema == "explicit-harm",
        )
    for corpus in corpora:
        _validate_counts(corpus)
        traces = corpus.traces[:args.limit] if args.limit else corpus.traces
        live_results = None
        variants = REPLAY_VARIANTS
        if evaluator is not None:
            cache_dir = args.output_dir / "deepseek-cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / (
                f"{corpus.name}-{args.deepseek_model}-{evaluator.schema_version}.jsonl"
            )
            cached = _load_live_cache(cache_path)
            before = len(cached)
            completed_new = 0

            def save_result(case_id: str, value: LiveSemanticDecision) -> None:
                nonlocal completed_new
                with cache_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(
                        live_semantic_decision_to_json(case_id, value), ensure_ascii=False,
                    ) + "\n")
                completed_new += 1
                if completed_new == 1 or completed_new % 50 == 0:
                    print(
                        f"{corpus.name}: {completed_new}/{len(traces) - before} new DeepSeek results",
                        flush=True,
                    )

            live_results = asyncio.run(
                evaluator.evaluate(traces, cached=cached, on_result=save_result)
            )
            selected = {trace.case_id: live_results[trace.case_id] for trace in traces}
            total_paid_calls += max(0, len(selected) - before)
            total_represented_calls += len(selected)
            total_input_tokens += sum(item.input_tokens for item in selected.values())
            total_output_tokens += sum(item.output_tokens for item in selected.values())
            total_failures += sum(item.status != "ok" for item in selected.values())
            variants = REPLAY_VARIANTS + LIVE_REPLAY_VARIANTS
        report = evaluate_replay(
            corpus.name, traces, variants=variants, live_decisions=live_results
        )
        report["source_metadata"] = dict(corpus.metadata)
        reports.append(report)
    config_json = json.dumps(PipelineConfig().__dict__, sort_keys=True, separators=(",", ":"))
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aegis_commit": _commit(REPO_ROOT),
        "aegis_worktree_dirty": _is_dirty(REPO_ROOT),
        "implementation_sha256": _implementation_sha256(),
        "agentdojo_commit": _commit(args.agentdojo_root) if args.agentdojo_root else None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pipeline_config_sha256": hashlib.sha256(config_json.encode()).hexdigest(),
        "network_sources": "official repositories/dataset cards listed in docs/BENCHMARK_RESEARCH.md",
        "tool_execution": "disabled",
        "baseline_status": {
            "deepseek_judge_live": "completed" if evaluator else "not_run_no_paid_api_authorization",
            "five_stage_immunity": "not_run_requires_leakage_safe_train_shadow_test_split",
        },
        "deepseek": {
            "model": args.deepseek_model if evaluator else None,
            "evidence_schema_version": evaluator.schema_version if evaluator else None,
            "includes_explicit_harm": evaluator.include_explicit_harm if evaluator else None,
            "paid_api_calls_for_result_set": total_represented_calls,
            "new_paid_api_calls_during_this_invocation": total_paid_calls,
            "api_responses_represented": total_represented_calls,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "failed_samples": total_failures,
            "estimated_cost_usd": round(
                total_input_tokens * 0.14 / 1_000_000
                + total_output_tokens * 0.28 / 1_000_000,
                6,
            ),
            "responses_reused_between_live_variants": True,
            "pricing_assumption_usd_per_million": {
                "input_cache_miss": 0.14,
                "output": 0.28,
            } if evaluator else None,
        },
    }
    paths = write_replay_reports(reports, args.output_dir, run_metadata=metadata)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
