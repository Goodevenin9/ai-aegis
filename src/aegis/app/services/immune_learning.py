"""Bounded, explainable immunity signals learned from confirmed attack sessions.

The engine never returns an allow/block verdict.  Candidate and shadow patterns
are observation-only, while active/decaying patterns may contribute a capped
risk delta that the deterministic Drift state machine consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, FrozenSet, Iterable, Literal, Mapping

AntibodyStatus = Literal["candidate", "shadow", "active", "decaying", "retired"]


@dataclass(frozen=True)
class BehaviorProfile:
    """Privacy-minimised structure extracted from one Agent session."""

    tool_sequence: tuple[str, ...] = ()
    capability_sequence: tuple[str, ...] = ()
    radius_sequence: tuple[str, ...] = ()
    features: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class AntibodyPattern:
    """One governed behavior signature; raw prompts and secrets are excluded."""

    antibody_id: str
    name: str
    status: AntibodyStatus = "candidate"
    tool_sequence: tuple[str, ...] = ()
    capability_sequence: tuple[str, ...] = ()
    radius_sequence: tuple[str, ...] = ()
    required_features: FrozenSet[str] = frozenset()
    optional_features: FrozenSet[str] = frozenset()
    similarity_threshold: float = 0.75
    max_score_delta: int = 20
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.antibody_id.strip() or not self.name.strip():
            raise ValueError("antibody id and name are required")
        if self.status not in {"candidate", "shadow", "active", "decaying", "retired"}:
            raise ValueError("invalid antibody status")
        if not 0.5 <= float(self.similarity_threshold) <= 1.0:
            raise ValueError("similarity threshold must be between 0.5 and 1.0")
        if not 0 <= int(self.max_score_delta) <= 30:
            raise ValueError("antibody score delta must be between 0 and 30")
        if not 0.0 <= float(self.weight) <= 1.0:
            raise ValueError("antibody weight must be between 0 and 1")


@dataclass(frozen=True)
class ImmuneMatch:
    antibody_id: str
    name: str
    status: AntibodyStatus
    similarity: float
    score_delta: int
    effective: bool
    matched_features: tuple[str, ...]


@dataclass(frozen=True)
class ImmuneMatchResult:
    matches: tuple[ImmuneMatch, ...]
    total_score_delta: int


def _lcs_ratio(expected: tuple[str, ...], observed: tuple[str, ...]) -> float:
    if not expected:
        return 1.0
    if not observed:
        return 0.0
    previous = [0] * (len(observed) + 1)
    for left in expected:
        current = [0]
        for index, right in enumerate(observed, start=1):
            if left.casefold() == right.casefold():
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1] / len(expected)


def _profile_similarity(
    pattern: AntibodyPattern, profile: BehaviorProfile
) -> tuple[float, tuple[str, ...]]:
    components: list[tuple[str, float, float]] = []
    if pattern.tool_sequence:
        components.append(
            ("tool_sequence", _lcs_ratio(pattern.tool_sequence, profile.tool_sequence), 0.35)
        )
    if pattern.capability_sequence:
        components.append(
            (
                "capability_sequence",
                _lcs_ratio(pattern.capability_sequence, profile.capability_sequence),
                0.30,
            )
        )
    if pattern.radius_sequence:
        components.append(
            ("radius_sequence", _lcs_ratio(pattern.radius_sequence, profile.radius_sequence), 0.20)
        )
    if pattern.required_features:
        required = len(pattern.required_features & profile.features) / len(pattern.required_features)
        components.append(("required_features", required, 0.10))
    if pattern.optional_features:
        optional = len(pattern.optional_features & profile.features) / len(pattern.optional_features)
        components.append(("optional_features", optional, 0.05))
    if not components:
        return 0.0, ()
    weight_total = sum(weight for _, _, weight in components)
    similarity = sum(value * weight for _, value, weight in components) / weight_total
    matched = tuple(name for name, value, _ in components if value > 0)
    return round(similarity, 4), matched


class ImmuneMatcher:
    """Match profiles without side effects and cap all learned-risk influence."""

    def __init__(
        self,
        antibodies: Iterable[AntibodyPattern] = (),
        *,
        max_total_score_delta: int = 25,
    ) -> None:
        self._antibodies = tuple(antibodies)
        self.max_total_score_delta = max(0, min(30, int(max_total_score_delta)))

    @property
    def antibodies(self) -> tuple[AntibodyPattern, ...]:
        return self._antibodies

    def match(self, profile: BehaviorProfile) -> ImmuneMatchResult:
        candidates: list[tuple[AntibodyPattern, float, tuple[str, ...]]] = []
        for antibody in self._antibodies:
            if antibody.status == "retired":
                continue
            similarity, features = _profile_similarity(antibody, profile)
            if similarity >= antibody.similarity_threshold:
                candidates.append((antibody, similarity, features))
        candidates.sort(key=lambda item: (-item[1], item[0].antibody_id))

        remaining = self.max_total_score_delta
        matches: list[ImmuneMatch] = []
        for antibody, similarity, features in candidates:
            effective = antibody.status in {"active", "decaying"}
            proposed = round(antibody.max_score_delta * similarity * antibody.weight)
            delta = min(max(0, proposed), remaining) if effective else 0
            remaining -= delta
            matches.append(
                ImmuneMatch(
                    antibody_id=antibody.antibody_id,
                    name=antibody.name,
                    status=antibody.status,
                    similarity=similarity,
                    score_delta=delta,
                    effective=effective and delta > 0,
                    matched_features=features,
                )
            )
        return ImmuneMatchResult(tuple(matches), self.max_total_score_delta - remaining)


_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"shadow", "retired"}),
    "shadow": frozenset({"active", "retired"}),
    "active": frozenset({"decaying", "retired", "shadow"}),
    "decaying": frozenset({"active", "retired", "shadow"}),
    "retired": frozenset(),
}


def transition_antibody(
    current: str,
    target: str,
    *,
    approved: bool,
) -> AntibodyStatus:
    """Validate the lifecycle, requiring approval for any effective state."""

    if target not in _TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid antibody transition: {current} -> {target}")
    if target in {"active", "decaying"} and not approved:
        raise ValueError("activation requires explicit approval")
    return target  # type: ignore[return-value]


def extract_behavior_profile(events: Iterable[Mapping[str, Any]]) -> BehaviorProfile:
    """Extract a privacy-minimised signature from verified runtime events."""

    tools: list[str] = []
    capabilities: list[str] = []
    radii: list[str] = []
    features: set[str] = set()
    capability_by_tool = {
        "read": "file_read", "grep": "file_read", "glob": "file_read", "ls": "file_read",
        "write": "file_write", "edit": "file_write", "bash": "shell_exec",
        "powershell": "shell_exec", "shell": "shell_exec", "exec": "shell_exec",
        "webfetch": "network_outbound", "websearch": "network_outbound",
    }
    for event in events:
        if event.get("event_type") != "before_tool_call":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        tool = str(payload.get("tool_name") or "unknown_tool")[:100]
        tools.append(tool)
        capabilities.append(capability_by_tool.get(tool.casefold(), "unknown_tool"))
        layers = payload.get("layers") if isinstance(payload.get("layers"), Mapping) else {}
        radius = layers.get("radius") if isinstance(layers.get("radius"), Mapping) else {}
        radii.append(str(radius.get("value") or "none")[:32])
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else []
        for signal in signals:
            if not isinstance(signal, Mapping):
                continue
            code = str(signal.get("code") or "")[:128]
            if code:
                features.add(code)
            if code == "boundary.shadow_file":
                features.add("sensitive_read")
            if "repeated" in code:
                features.add("repeated_retry")
            if code.startswith("capability."):
                features.add("capability_escalation")
            if code.startswith("radius.") and not code.endswith(".project"):
                features.add("radius_expansion")
    if not tools:
        raise ValueError("session contains no tool-call behavior to learn")
    return BehaviorProfile(
        tool_sequence=tuple(tools[-32:]),
        capability_sequence=tuple(capabilities[-32:]),
        radius_sequence=tuple(radii[-32:]),
        features=frozenset(features),
    )


__all__ = [
    "AntibodyPattern",
    "AntibodyStatus",
    "BehaviorProfile",
    "ImmuneMatch",
    "ImmuneMatcher",
    "ImmuneMatchResult",
    "transition_antibody",
    "extract_behavior_profile",
]
