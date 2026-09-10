"""Public behavior tests for the bounded session-immunity engine."""

from aegis.app.services.immune_learning import (
    AntibodyPattern,
    BehaviorProfile,
    ImmuneMatcher,
    transition_antibody,
    extract_behavior_profile,
)
from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.migrations import run_migrations
from aegis.app.database.repositories.immune_learning import ImmuneLearningRepository

import pytest


def _profile() -> BehaviorProfile:
    return BehaviorProfile(
        tool_sequence=("Read", "Bash", "WebFetch"),
        capability_sequence=("file_read", "shell_exec", "network_outbound"),
        radius_sequence=("project", "system", "external"),
        features=frozenset({"repeated_retry", "sensitive_read"}),
    )


def _antibody(status: str = "active", max_score_delta: int = 20) -> AntibodyPattern:
    return AntibodyPattern(
        antibody_id="ab-exfil-1",
        name="progressive exfiltration",
        status=status,
        tool_sequence=("Read", "Bash", "WebFetch"),
        capability_sequence=("file_read", "shell_exec", "network_outbound"),
        radius_sequence=("project", "system", "external"),
        required_features=frozenset({"sensitive_read"}),
        optional_features=frozenset({"repeated_retry"}),
        similarity_threshold=0.70,
        max_score_delta=max_score_delta,
    )


def test_active_antibody_returns_explainable_bounded_risk_evidence():
    result = ImmuneMatcher((_antibody(max_score_delta=20),)).match(_profile())

    assert result.total_score_delta == 20
    assert result.matches[0].antibody_id == "ab-exfil-1"
    assert result.matches[0].similarity == 1.0
    assert result.matches[0].effective is True
    assert "tool_sequence" in result.matches[0].matched_features


def test_candidate_and_shadow_antibodies_observe_without_affecting_risk():
    matcher = ImmuneMatcher((_antibody("candidate"), _antibody("shadow")))

    result = matcher.match(_profile())

    assert result.total_score_delta == 0
    assert [match.effective for match in result.matches] == [False, False]


def test_multiple_antibodies_cannot_exceed_session_immunity_cap():
    first = _antibody(max_score_delta=20)
    second = AntibodyPattern(**{**first.__dict__, "antibody_id": "ab-exfil-2"})

    result = ImmuneMatcher((first, second), max_total_score_delta=25).match(_profile())

    assert result.total_score_delta == 25
    assert sum(match.score_delta for match in result.matches) == 25


def test_antibody_lifecycle_requires_shadow_and_approval_before_activation():
    assert transition_antibody("candidate", "shadow", approved=False) == "shadow"
    assert transition_antibody("shadow", "active", approved=True) == "active"

    try:
        transition_antibody("candidate", "active", approved=True)
    except ValueError as exc:
        assert "invalid antibody transition" in str(exc)
    else:
        raise AssertionError("candidate antibodies must never activate directly")


@pytest.mark.asyncio
async def test_repository_persists_governed_lifecycle_and_reloadable_matcher(tmp_path):
    db = DatabaseConnection(tmp_path / "immune.db")
    await run_migrations(db)
    repository = ImmuneLearningRepository(db)

    created = await repository.create_candidate(
        name="progressive exfiltration",
        profile=_profile(),
        source_session_key="codex\0attack-1",
        source_evidence_ids=["event-1"],
    )
    assert created["status"] == "candidate"

    shadow = await repository.transition(created["antibody_id"], "shadow")
    assert shadow["status"] == "shadow"

    with pytest.raises(ValueError, match="approval"):
        await repository.transition(created["antibody_id"], "active")

    active = await repository.transition(
        created["antibody_id"], "active", approved_by="security-admin"
    )
    matcher = await repository.load_matcher()

    assert active["status"] == "active"
    assert matcher.match(_profile()).total_score_delta > 0
    await db.disconnect()


def test_confirmed_session_events_are_reduced_to_behavior_not_raw_prompt_content():
    profile = extract_behavior_profile(
        [
            {
                "event_type": "before_tool_call",
                "content": "raw secret must not be learned",
                "payload": {
                    "tool_name": "Read",
                    "layers": {"radius": {"value": "project"}},
                    "signals": [],
                },
            },
            {
                "event_type": "before_tool_call",
                "payload": {
                    "tool_name": "Bash",
                    "layers": {"radius": {"value": "system"}},
                    "signals": [{"code": "drift.repeated_risky_action"}],
                },
            },
        ]
    )

    assert profile.tool_sequence == ("Read", "Bash")
    assert profile.capability_sequence == ("file_read", "shell_exec")
    assert "repeated_retry" in profile.features
    assert "secret" not in repr(profile)
