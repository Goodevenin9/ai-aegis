"""Runtime endpoints for intent observation and five-stage PreToolUse decisions."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

from aegis.app.database.connection import DatabaseConnection
from aegis.app.database.repositories.runtime_sessions import RuntimeSessionRepository
from aegis.app.database.repositories.immune_learning import ImmuneLearningRepository
from aegis.app.database.repositories.runtime_policy import RuntimePolicyRepository
from aegis.app.services.pretool_pipeline import (
    KNOWN_CAPABILITIES,
    PipelineConfig,
    PreToolContext,
    SemanticLabels,
    SessionDriftStore,
    run_pretool_pipeline,
    required_capability,
)
from aegis.app.services.immune_learning import (
    BehaviorProfile, ImmuneMatch, ImmuneMatchResult, ImmuneMatcher,
    extract_behavior_profile,
)
from aegis.app.services.semantic_evidence import (
    DeepSeekSemanticExtractor,
    should_run_focused_verifier,
)
from aegis.app.services.pipeline_evaluation import VARIANTS, evaluate_variants, load_cases

router = APIRouter(prefix="/runtime")
_store = SessionDriftStore()
_extractor = DeepSeekSemanticExtractor()
_repository: Optional[RuntimeSessionRepository] = None
_policy_repository: Optional[RuntimePolicyRepository] = None
_immune_repository: Optional[ImmuneLearningRepository] = None
_immune_matcher = ImmuneMatcher()
_immune_loaded = False
_hydrated: set[str] = set()
logger = logging.getLogger(__name__)


def _session_key(runtime_kind: str, session_id: str) -> str:
    """Namespace runtime-owned session ids before they reach shared state."""

    return f"{runtime_kind.strip().lower() or 'unknown'}\0{session_id}"


class IntentObservationRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    text: str = Field(..., min_length=1, max_length=16_000)
    runtime_kind: str = Field(default="unknown", max_length=64)
    allowed_capabilities: list[str] = Field(default_factory=list, max_length=32)


class PreToolDecisionRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=200)
    tool_input: dict[str, Any] = Field(default_factory=dict)
    session_id: str = Field(default="__anonymous__", max_length=128)
    runtime_kind: str = Field(default="unknown", max_length=64)
    base_decision: Literal["allow", "ask", "deny"] = "allow"
    allowed_capabilities: list[str] = Field(default_factory=list, max_length=32)
    project_root: Optional[str] = Field(default=None, max_length=1000)
    headless: bool = False
    manifest_id: str = Field(default="default", min_length=1, max_length=128)


class PipelineConfigRequest(BaseModel):
    confirm_threshold: int = Field(default=40, ge=1, le=99)
    block_threshold: int = Field(default=80, ge=2, le=100)
    theme_shift_weight: int = Field(default=20, ge=0, le=100)
    permission_probe_weight: int = Field(default=20, ge=0, le=100)
    request_escalation_weight: int = Field(default=20, ge=0, le=100)
    explicit_harm_weight: int = Field(default=20, ge=0, le=100)
    unauthorized_target_weight: int = Field(default=0, ge=0, le=100)
    deception_or_evasion_weight: int = Field(default=0, ge=0, le=100)
    irreversible_impact_weight: int = Field(default=5, ge=0, le=100)
    harm_verified_weight: int = Field(default=20, ge=0, le=100)
    intent_capability_weight: int = Field(default=10, ge=0, le=100)
    harmful_high_impact_weight: int = Field(default=20, ge=0, le=100)
    harmful_external_write_weight: int = Field(default=10, ge=0, le=100)
    sensitive_sequence_weight: int = Field(default=15, ge=0, le=100)
    repeated_retry_weight: int = Field(default=15, ge=0, le=100)
    third_retry_weight: int = Field(default=30, ge=0, le=100)
    safe_turn_decay: int = Field(default=10, ge=0, le=100)
    max_drift_score: int = Field(default=100, ge=1, le=100)
    max_immune_session_score: int = Field(default=25, ge=0, le=30)


class AntibodyCandidateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tool_sequence: list[str] = Field(default_factory=list, max_length=32)
    capability_sequence: list[str] = Field(default_factory=list, max_length=32)
    radius_sequence: list[str] = Field(default_factory=list, max_length=32)
    features: list[str] = Field(default_factory=list, max_length=64)
    source_session_key: Optional[str] = Field(default=None, max_length=256)
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=128)
    similarity_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    max_score_delta: int = Field(default=20, ge=0, le=30)


class AntibodyTransitionRequest(BaseModel):
    target: Literal["shadow", "active", "decaying", "retired"]
    approved_by: Optional[str] = Field(default=None, max_length=200)


class AntibodyFromSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    runtime_kind: str = Field(default="unknown", max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=128)
    similarity_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    max_score_delta: int = Field(default=20, ge=0, le=30)


class CapabilityManifestRequest(BaseModel):
    allowed_capabilities: list[str] = Field(default_factory=list, max_length=32)
    project_root: Optional[str] = Field(default=None, max_length=1000)
    description: str = Field(default="", max_length=500)
    session_id: str = Field(default="*", min_length=1, max_length=128)


class TrustGrantRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    runtime_kind: str = Field(default="unknown", max_length=64)
    capability: str = Field(..., min_length=1, max_length=100)
    ttl_seconds: int = Field(default=300, ge=1, le=3600)
    max_uses: int = Field(default=5, ge=1, le=100)


class EvaluationRequest(BaseModel):
    variants: list[str] = Field(
        default_factory=lambda: ["aegis_single_turn", "deepseek_judge_recorded", "five_stage"],
        min_length=1,
        max_length=3,
    )
    include_details: bool = False


RuntimeEventType = Literal[
    "before_prompt_build",
    "llm_input",
    "llm_output",
    "before_tool_call",
    "after_tool_call",
]


class RuntimeEventRequest(BaseModel):
    """One normalized event from an Agent hook or LLM proxy adapter."""

    session_id: str = Field(..., min_length=1, max_length=128)
    runtime_kind: str = Field(default="unknown", max_length=64)
    event_type: RuntimeEventType
    turn_index: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    text: Optional[str] = Field(default=None, max_length=16_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


def configure_runtime_repository(db: DatabaseConnection) -> None:
    """Attach durable storage after the application has run migrations."""

    global _repository, _policy_repository, _immune_repository, _immune_loaded
    _repository = RuntimeSessionRepository(db)
    _policy_repository = RuntimePolicyRepository(db)
    _immune_repository = ImmuneLearningRepository(db)
    _immune_loaded = False
    _hydrated.clear()


async def refresh_immune_matcher() -> None:
    global _immune_matcher, _immune_loaded
    if _immune_repository:
        _immune_matcher = await _immune_repository.load_matcher()
    else:
        _immune_matcher = ImmuneMatcher()
    _immune_loaded = True


async def _ensure_hydrated(session_key: str) -> None:
    if not _repository or session_key in _hydrated:
        return
    snapshot = await _repository.load_state(session_key)
    if snapshot is None:
        snapshot = await _repository.recover_state_from_events(session_key)
    if snapshot:
        _store.restore(session_key, snapshot)
    _hydrated.add(session_key)


async def _persist_state(session_key: str, runtime_kind: str, session_id: str) -> None:
    if not _repository:
        return
    await _repository.save_state(
        session_key=session_key,
        runtime_kind=runtime_kind,
        session_id=session_id,
        state=_store.snapshot(session_key),
    )


async def _extract_and_queue(
    session_key: str,
    runtime_kind: str,
    session_id: str,
    original_intent: str,
    current_text: str,
    expected_intent_revision: int,
) -> None:
    result = await _extractor.extract(original_intent, current_text)
    if result.status == "ok":
        verifier_result = None
        should_verify = bool(
            result.evidence is not None
            and should_run_focused_verifier(result.evidence)
        )
        if should_verify and getattr(_extractor, "verifier_enabled", False):
            verifier_result = await _extractor.verify_harm(original_intent, current_text)
            if verifier_result.status == "failed":
                logger.warning(
                    "DeepSeek focused verifier failed for session %s: %s",
                    session_key,
                    verifier_result.error,
                )
        # Both model requests may finish after a newer prompt. Commit the
        # evidence group only when it still belongs to the active intent turn.
        if _store.get(session_key).intent_revision != expected_intent_revision:
            logger.info(
                "Discarded stale semantic evidence for session %s revision %s",
                session_key,
                expected_intent_revision,
            )
            return
        if result.evidence is not None:
            _store.observe_intent_evidence(session_key, result.evidence)
        else:
            _store.observe_semantic_labels(session_key, result.labels)
        if (
            verifier_result is not None
            and verifier_result.status == "ok"
            and verifier_result.labels.harm_verified
        ):
            _store.observe_semantic_labels(session_key, verifier_result.labels)
        await _persist_state(session_key, runtime_kind, session_id)
        if _repository:
            await _repository.append_event(
                session_key=session_key,
                runtime_kind=runtime_kind,
                session_id=session_id,
                event_type="semantic_evidence",
                payload={
                    "status": result.status,
                    "labels": result.labels.__dict__,
                    "focused_verifier": (
                        {
                            "status": verifier_result.status,
                            "labels": verifier_result.labels.__dict__,
                            "error": verifier_result.error,
                        }
                        if verifier_result is not None else None
                    ),
                    "intent_evidence": (
                        {
                            "requested_capabilities": sorted(
                                result.evidence.requested_capabilities
                            ),
                            "requested_radius": result.evidence.requested_radius,
                        }
                        if result.evidence is not None else None
                    ),
                    "state_snapshot": _store.snapshot(session_key),
                },
            )
    elif result.status == "failed":
        logger.warning(
            "DeepSeek semantic evidence failed for session %s: %s",
            session_key,
            result.error,
        )


@router.post("/intent", status_code=202)
async def observe_intent(
    request: IntentObservationRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Observe a turn and queue optional DeepSeek extraction after responding."""

    if request.session_id == "__anonymous__":
        return {
            "status": "skipped_anonymous",
            "error": None,
            "labels": SemanticLabels().__dict__,
            "llm_enabled": _extractor.enabled,
        }
    session_key = _session_key(request.runtime_kind, request.session_id)
    await _ensure_hydrated(session_key)
    capabilities = frozenset(
        value.strip() for value in request.allowed_capabilities if value.strip()
    )
    is_first_turn = _store.get(session_key).original_intent is None
    state = _store.observe_intent(session_key, request.text, capabilities)
    await _persist_state(session_key, request.runtime_kind, request.session_id)
    if _repository:
        await _repository.append_event(
            session_key=session_key,
            runtime_kind=request.runtime_kind,
            session_id=request.session_id,
            event_type="before_prompt_build",
            turn_index=state.intent_revision,
            content=request.text,
            payload={
                "source": "intent_endpoint",
                "state_snapshot": _store.snapshot(session_key),
            },
        )
    if not is_first_turn and state.original_intent:
        background_tasks.add_task(
            _extract_and_queue,
            session_key,
            request.runtime_kind,
            request.session_id,
            state.original_intent,
            request.text,
            state.intent_revision,
        )
        result_status = "queued" if _extractor.enabled else "disabled"
    else:
        result_status = "baseline"
    return {
        "status": result_status,
        "error": None,
        "labels": SemanticLabels().__dict__,
        "llm_enabled": _extractor.enabled,
    }


@router.post("/events", status_code=202)
async def observe_runtime_event(
    request: RuntimeEventRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Persist one intent/behaviour event and update intent state when relevant."""

    if request.session_id == "__anonymous__":
        return {"status": "skipped_anonymous", "event_type": request.event_type}
    session_key = _session_key(request.runtime_kind, request.session_id)
    await _ensure_hydrated(session_key)
    state = _store.get(session_key)
    status = "recorded"
    semantic_candidate = request.event_type in {
        "before_prompt_build", "llm_input", "llm_output"
    }
    if request.event_type in {"before_prompt_build", "llm_input"} and request.text:
        is_first_turn = state.original_intent is None
        state = _store.observe_intent(session_key, request.text)
        status = "baseline" if is_first_turn else "queued"
        await _persist_state(session_key, request.runtime_kind, request.session_id)
    if _repository:
        await _repository.append_event(
            session_key=session_key,
            runtime_kind=request.runtime_kind,
            session_id=request.session_id,
            event_type=request.event_type,
            turn_index=request.turn_index or state.intent_revision or None,
            content=request.text,
            payload={
                **request.metadata,
                "state_snapshot": _store.snapshot(session_key),
            },
        )
    if semantic_candidate and request.text and state.original_intent and (
        request.text != state.original_intent
    ):
        background_tasks.add_task(
            _extract_and_queue,
            session_key,
            request.runtime_kind,
            request.session_id,
            state.original_intent,
            request.text,
            state.intent_revision,
        )
        status = "queued" if _extractor.enabled else "recorded"
    return {
        "status": status,
        "event_type": request.event_type,
        "llm_enabled": _extractor.enabled,
    }


@router.post("/pretool/decide")
async def decide_pretool(request: PreToolDecisionRequest) -> dict[str, Any]:
    """Run the five stages; no LLM call occurs on this hot path."""

    # Do not let unrelated hosts without session identifiers contaminate one
    # another's drift score. Anonymous calls still receive all stateless layers.
    store = _store if request.session_id != "__anonymous__" else SessionDriftStore()
    session_key = _session_key(request.runtime_kind, request.session_id)
    if request.session_id != "__anonymous__":
        await _ensure_hydrated(session_key)
    state = store.get(session_key)
    supplied_capabilities = frozenset(
        value.strip() for value in request.allowed_capabilities if value.strip()
    )
    manifest = None
    if _policy_repository:
        for runtime_kind, session_id in (
            (request.runtime_kind, request.session_id),
            (request.runtime_kind, "*"),
            ("default", request.session_id),
            ("default", "*"),
        ):
            manifest = await _policy_repository.get_manifest(
                runtime_kind, request.manifest_id, session_id
            )
            if manifest:
                break
    capabilities = (
        frozenset(manifest["allowed_capabilities"])
        if manifest else supplied_capabilities
    )
    if not capabilities:
        capabilities = state.allowed_capabilities
    needed_capability = required_capability(request.tool_name)
    trust_reused = (
        request.session_id != "__anonymous__"
        and needed_capability not in capabilities
        and store.consume_trusted_capability(session_key, needed_capability)
    )
    trusted_capabilities = frozenset({needed_capability}) if trust_reused else frozenset()
    capabilities = capabilities | trusted_capabilities
    effective_project_root = request.project_root or (
        manifest.get("project_root") if manifest else None
    )
    project_root = Path(effective_project_root) if effective_project_root else None
    configured_headless = os.environ.get("AEGIS_HEADLESS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    config = await _policy_repository.get_config() if _policy_repository else PipelineConfig()
    if not _immune_loaded:
        await refresh_immune_matcher()
    decision = run_pretool_pipeline(
        PreToolContext(
            tool_name=request.tool_name,
            tool_input=request.tool_input,
            session_id=session_key,
            runtime_kind=request.runtime_kind,
            base_decision=request.base_decision,
            allowed_capabilities=capabilities,
            project_root=project_root,
            headless=request.headless or configured_headless,
        ),
        store,
        config,
        immune_matcher=_immune_matcher,
    )
    result = decision.to_dict()
    result["policy"] = {
        "manifest_id": request.manifest_id if manifest else None,
        "manifest_version": manifest.get("version") if manifest else None,
        "trusted_capabilities_reused": sorted(trusted_capabilities),
    }
    if request.session_id != "__anonymous__":
        if _immune_repository and decision.immune_matches:
            await _immune_repository.record_matches(
                session_key,
                ImmuneMatchResult(
                    matches=tuple(
                        ImmuneMatch(
                            antibody_id=str(item["antibody_id"]),
                            name=str(item["name"]),
                            status=str(item["status"]),  # type: ignore[arg-type]
                            similarity=float(item["similarity"]),
                            score_delta=int(item["score_delta"]),
                            effective=bool(item["effective"]),
                            matched_features=tuple(item.get("matched_features") or ()),
                        )
                        for item in decision.immune_matches
                    ),
                    total_score_delta=sum(
                        int(item["score_delta"]) for item in decision.immune_matches
                    ),
                ),
            )
        await _persist_state(session_key, request.runtime_kind, request.session_id)
        if _repository:
            await _repository.append_event(
                session_key=session_key,
                runtime_kind=request.runtime_kind,
                session_id=request.session_id,
                event_type="before_tool_call",
                turn_index=state.intent_revision or None,
                content=json.dumps(request.tool_input, ensure_ascii=False, sort_keys=True),
                payload={
                    "tool_name": request.tool_name,
                    **result,
                    "state_snapshot": _store.snapshot(session_key),
                },
            )
    return result


@router.get("/config")
async def get_pipeline_config() -> dict[str, Any]:
    config = await _policy_repository.get_config() if _policy_repository else PipelineConfig()
    return {"config": config.__dict__, "persistent": _policy_repository is not None}


@router.put("/config")
async def update_pipeline_config(
    request: PipelineConfigRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(x_aegis_ui_token)
    raise HTTPException(
        status_code=409,
        detail=(
            "Direct policy writes are disabled; create a policy_change Security Agent run, "
            "review its simulation, and approve the exact proposal hash"
        ),
    )


@router.get("/immunity/antibodies")
async def list_antibodies(status: Optional[str] = None) -> dict[str, Any]:
    antibodies = await _immune_repository.list(status) if _immune_repository else []
    return {"antibodies": antibodies, "total": len(antibodies)}


@router.post("/immunity/antibodies", status_code=201)
async def create_antibody_candidate(
    request: AntibodyCandidateRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(x_aegis_ui_token)
    if not _immune_repository:
        raise HTTPException(status_code=503, detail="immunity persistence unavailable")
    if not (request.tool_sequence or request.capability_sequence or request.features):
        raise HTTPException(status_code=422, detail="antibody pattern cannot be empty")
    result = await _immune_repository.create_candidate(
        name=request.name,
        description=request.description,
        profile=BehaviorProfile(
            tool_sequence=tuple(request.tool_sequence),
            capability_sequence=tuple(request.capability_sequence),
            radius_sequence=tuple(request.radius_sequence),
            features=frozenset(request.features),
        ),
        source_session_key=request.source_session_key,
        source_evidence_ids=request.source_evidence_ids,
        similarity_threshold=request.similarity_threshold,
        max_score_delta=request.max_score_delta,
    )
    await refresh_immune_matcher()
    return result


@router.post("/immunity/from-session", status_code=201)
async def create_antibody_from_session(
    request: AntibodyFromSessionRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Learn a candidate only from an intact, explicitly selected session."""

    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(x_aegis_ui_token)
    if not _immune_repository or not _repository:
        raise HTTPException(status_code=503, detail="immunity persistence unavailable")
    session_key = _session_key(request.runtime_kind, request.session_id)
    integrity = await _repository.verify_event_chain(session_key)
    if not integrity["valid"]:
        raise HTTPException(status_code=409, detail="cannot learn from a broken audit chain")
    events = await _repository.get_timeline(session_key, 2000)
    try:
        profile = extract_behavior_profile(events)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await _immune_repository.create_candidate(
        name=request.name,
        description=request.description,
        profile=profile,
        source_session_key=session_key,
        source_evidence_ids=request.source_evidence_ids,
        similarity_threshold=request.similarity_threshold,
        max_score_delta=request.max_score_delta,
    )
    await refresh_immune_matcher()
    return result


@router.post("/immunity/antibodies/{antibody_id}/transition")
async def transition_antibody_status(
    antibody_id: str,
    request: AntibodyTransitionRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(x_aegis_ui_token)
    if not _immune_repository:
        raise HTTPException(status_code=503, detail="immunity persistence unavailable")
    try:
        result = await _immune_repository.transition(
            antibody_id,
            request.target,
            approved_by=request.approved_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="antibody not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await refresh_immune_matcher()
    return result


@router.get("/immunity/matches")
async def list_immune_matches(
    session_key: Optional[str] = None, limit: int = 100
) -> dict[str, Any]:
    matches = (
        await _immune_repository.list_matches(session_key=session_key, limit=limit)
        if _immune_repository else []
    )
    return {"matches": matches, "total": len(matches)}


@router.get("/manifests")
async def list_capability_manifests() -> dict[str, Any]:
    manifests = await _policy_repository.list_manifests() if _policy_repository else []
    return {"manifests": manifests, "known_capabilities": sorted(KNOWN_CAPABILITIES)}


@router.put("/manifests/{runtime_kind}/{manifest_id}")
async def update_capability_manifest(
    runtime_kind: str,
    manifest_id: str,
    request: CapabilityManifestRequest,
) -> dict[str, Any]:
    if not _policy_repository:
        raise HTTPException(status_code=503, detail="runtime policy persistence unavailable")
    try:
        return await _policy_repository.save_manifest(
            runtime_kind.strip().lower() or "unknown",
            manifest_id,
            request.allowed_capabilities,
            request.project_root,
            request.description,
            request.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/manifests/{runtime_kind}/{manifest_id}")
async def delete_capability_manifest(
    runtime_kind: str, manifest_id: str, session_id: str = "*"
) -> dict[str, Any]:
    if not _policy_repository:
        raise HTTPException(status_code=503, detail="runtime policy persistence unavailable")
    deleted = await _policy_repository.delete_manifest(runtime_kind, manifest_id, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="capability manifest not found")
    return {"deleted": True, "runtime_kind": runtime_kind, "manifest_id": manifest_id}


@router.post("/trust/grants", status_code=201)
async def grant_session_trust(
    request: TrustGrantRequest,
    x_aegis_ui_token: Optional[str] = Header(None),
) -> dict[str, Any]:
    from aegis.app.server.routes.jit_access import _require_ui_token

    _require_ui_token(x_aegis_ui_token)
    if request.session_id == "__anonymous__":
        raise HTTPException(status_code=422, detail="anonymous sessions cannot receive trust")
    if request.capability not in KNOWN_CAPABILITIES:
        raise HTTPException(status_code=422, detail="unknown capability")
    session_key = _session_key(request.runtime_kind, request.session_id)
    await _ensure_hydrated(session_key)
    _store.grant_trust(
        session_key,
        request.capability,
        request.ttl_seconds,
        request.max_uses,
    )
    await _persist_state(session_key, request.runtime_kind, request.session_id)
    if _repository:
        await _repository.append_event(
            session_key=session_key,
            runtime_kind=request.runtime_kind,
            session_id=request.session_id,
            event_type="trust_granted",
            payload={
                "capability": request.capability,
                "ttl_seconds": request.ttl_seconds,
                "max_uses": request.max_uses,
                "state_snapshot": _store.snapshot(session_key),
            },
        )
    return {
        "granted": True,
        "capability": request.capability,
        "ttl_seconds": request.ttl_seconds,
        "max_uses": request.max_uses,
    }


@router.get("/evaluations/dataset")
async def get_evaluation_dataset_summary() -> dict[str, Any]:
    cases = load_cases()
    return {
        "dataset": "chinese_agent_security_p1",
        "case_count": len(cases),
        "malicious": sum(1 for case in cases if case["malicious"]),
        "benign": sum(1 for case in cases if not case["malicious"]),
        "variants": sorted(VARIANTS),
    }


@router.post("/evaluations")
async def run_pipeline_evaluation(request: EvaluationRequest) -> dict[str, Any]:
    config = await _policy_repository.get_config() if _policy_repository else PipelineConfig()
    try:
        return evaluate_variants(
            request.variants, config=config, include_details=request.include_details
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions")
async def list_runtime_sessions(limit: int = 100) -> dict[str, Any]:
    """List durable session-security summaries for the local UI."""

    sessions = await _repository.list_sessions(limit) if _repository else []
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_runtime_session(
    session_id: str,
    runtime_kind: str = "unknown",
    limit: int = 500,
) -> dict[str, Any]:
    """Return one session's risk curve, causal timeline and chain integrity."""

    if not _repository:
        raise HTTPException(status_code=503, detail="runtime persistence unavailable")
    session_key = _session_key(runtime_kind, session_id)
    snapshot = await _repository.load_state(session_key)
    events = await _repository.get_timeline(session_key, limit)
    if snapshot is None:
        snapshot = await _repository.recover_state_from_events(session_key)
    risk_curve = [
        {
            "seq": event["seq"],
            "turn_index": event["turn_index"],
            "drift_score": event["payload"]["drift_score"],
            "action": event["payload"].get("action"),
        }
        for event in events
        if isinstance(event.get("payload", {}).get("drift_score"), (int, float))
    ]
    if snapshot is None and not events:
        raise HTTPException(status_code=404, detail="runtime session not found")
    return {
        "session_id": session_id,
        "runtime_kind": runtime_kind,
        "state": snapshot or {},
        "events": events,
        "risk_curve": risk_curve,
        "integrity": await _repository.verify_event_chain(session_key),
    }


@router.delete("/sessions/{session_id}")
async def reset_session(session_id: str, runtime_kind: str = "unknown") -> dict[str, Any]:
    """Forget ephemeral drift state for a completed or abandoned session."""

    _store.reset(_session_key(runtime_kind, session_id))
    _hydrated.discard(_session_key(runtime_kind, session_id))
    if _repository:
        await _repository.delete_session(_session_key(runtime_kind, session_id))
    return {"reset": True, "session_id": session_id, "runtime_kind": runtime_kind}


__all__ = ["configure_runtime_repository", "router"]
