"""Run the committed developer-workflow corpus through AI Aegis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aegis.app.services.developer_workflow_evaluation import (  # noqa: E402
    DEFAULT_DATASET,
    evaluate_developer_workflows,
    write_developer_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay safe developer workflows without executing tools.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "reports" / "developer-workflows-v1",
    )
    args = parser.parse_args()
    result = evaluate_developer_workflows(dataset_path=args.dataset)
    write_developer_reports(result, args.output_dir)
    print(f"Developer benchmark: {result['case_count']} cases")
    for profile in result["profiles"]:
        print(
            f"{profile['profile']}: disruption={profile['routine_developer_disruption_rate']:.2%}, "
            f"hard_block={profile['routine_hard_block_rate']:.2%}, "
            f"sensitive_review={profile['sensitive_review_rate']:.2%}, "
            f"dangerous_protection={profile['dangerous_protection_rate']:.2%}"
        )
    print(f"Reports: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
