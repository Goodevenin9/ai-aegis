"""P1 Chinese corpus and A/B evaluation contracts."""

from pathlib import Path

from aegis.app.services.pipeline_evaluation import evaluate_variants, load_cases


def test_p1_dataset_has_50_or_more_mixed_chinese_cases():
    cases = load_cases()

    assert 50 <= len(cases) <= 80
    assert any(case["malicious"] for case in cases)
    assert any(not case["malicious"] for case in cases)
    assert any("链" in case["id"] or case["id"].startswith("chain-") for case in cases)


def test_ab_evaluation_reports_recall_false_positive_and_actions():
    report = evaluate_variants(
        ["aegis_single_turn", "deepseek_judge_recorded", "five_stage"]
    )

    assert report["case_count"] >= 50
    assert [item["variant"] for item in report["results"]] == [
        "aegis_single_turn", "deepseek_judge_recorded", "five_stage"
    ]
    for item in report["results"]:
        assert 0 <= item["attack_recall"] <= 1
        assert 0 <= item["benign_false_positive_rate"] <= 1
        assert sum(item["actions"].values()) == report["case_count"]


def test_dataset_contains_explicit_benign_allow_examples():
    report = evaluate_variants(["five_stage"], include_details=True)
    by_id = {item["id"]: item for item in report["results"][0]["details"]}

    assert by_id["safe-01"]["action"] == "allow"
    assert by_id["safe-08"]["action"] == "allow"
    assert by_id["safe-19"]["action"] == "allow"


def test_p1_dataset_is_in_source_and_wheel_packaging_manifests():
    repo = Path(__file__).parents[3]
    manifest = (repo / "MANIFEST.in").read_text(encoding="utf-8")
    setup = (repo / "setup.py").read_text(encoding="utf-8")

    assert "benchmarks/chinese_agent_security_p1.jsonl" in manifest
    assert "benchmarks/chinese_agent_security_p1.jsonl" in setup
