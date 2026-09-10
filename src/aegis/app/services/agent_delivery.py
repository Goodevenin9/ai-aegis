"""Read-only delivery artifacts and server-side model credential configuration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def read_model_key() -> str:
    value = os.environ.get("AEGIS_DEEPSEEK_API_KEY")
    if value:
        return value.strip()
    filename = os.environ.get("AEGIS_DEEPSEEK_API_KEY_FILE")
    if not filename:
        return os.environ.get("DEEPSEEK_API_KEY", "").strip()
    try:
        path = Path(filename)
        if path.stat().st_size > 4096:
            return ""
        return path.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        return ""


def load_external_results() -> dict[str, Any]:
    configured = os.environ.get("AEGIS_BENCHMARK_REPORT")
    path = Path(configured) if configured else (
        Path(__file__).resolve().parents[4] / "reports" / "external-benchmarks"
        / "external_benchmark_results.json"
    )
    if not path.is_file():
        return {"status": "unavailable", "reason": "Benchmark report has not been installed"}
    if path.stat().st_size > 5_000_000:
        raise ValueError("Benchmark report exceeds size limit")
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("benchmarks"), list):
        raise ValueError("Invalid benchmark report schema")
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "status": "available", "report_sha256": digest,
        "citation": f"benchmark:{digest}",
        "run_metadata": data.get("run_metadata", {}),
        "benchmarks": data["benchmarks"],
        "limitations": [
            "Offline oracle replay, not native ASR or task utility",
            "Judge and semantic labels share a model response",
            "Reported local baseline does not establish Guardian performance",
        ],
    }


def export_run(run: dict[str, Any], format: str = "markdown") -> str:
    if format == "json":
        return json.dumps(run, ensure_ascii=False, indent=2)
    result = run.get("result") or {}
    lines = ["# AI Aegis 安全调查报告", "", f"报告编号：{run['run_id']}",
             f"状态：{run['status']}", "", str(result.get("summary") or "尚无结论"), ""]
    for title, value in (("分析", result.get("analysis")), ("评测", result.get("evaluation")),
                         ("证据引用", result.get("citations")), ("执行记录", run.get("events"))):
        lines.extend([f"## {title}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)
