"""Deployable FastAPI control plane for AI Aegis managed devices."""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from aegis.app.services.bundle_verifier import sign_bundle
from aegis.control_plane.config import ControlPlaneSettings
from aegis.control_plane.store import ControlPlaneStore


class EnrollmentTokenRequest(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class ApiKeyRequest(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    name: str = Field(default="integration", min_length=1, max_length=120)


class AnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=200_000)
    user_tier: str = "professional"
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutputAnalyzeRequest(BaseModel):
    output: str = Field(min_length=1, max_length=200_000)
    tier: str = "professional"
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_format: str = "text"
    scan_types: list[str] = Field(default_factory=lambda: ["pii", "secrets", "injection"])
    enable_masking: bool = True
    enable_ml_validation: bool = True
    model_id: Optional[str] = None
    conversation_id: Optional[str] = None


class RulesSyncRequest(BaseModel):
    tier: Literal["community", "professional", "enterprise"] = "community"


class EnrollmentRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=200)
    enrollment_token: str = Field(min_length=8)
    hostname: Optional[str] = Field(default=None, max_length=200)
    os: Optional[str] = Field(default=None, max_length=100)
    app_version: Optional[str] = Field(default=None, max_length=50)


class ManagedRule(BaseModel):
    tool_id: str = Field(min_length=1, max_length=200)
    effect: Literal["allow", "deny", "prompt"]
    priority: int = Field(default=0, ge=-10000, le=10000)
    reason: Optional[str] = Field(default=None, max_length=1000)


class PolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: Literal["audit", "enforce"] = "enforce"
    rules: list[ManagedRule] = Field(default_factory=list, max_length=5000)


class AppliedRequest(BaseModel):
    bundle_id: str
    policy_id: str
    version: int
    device_id: str
    org_id: str
    applied_at: str
    status: Literal["ok", "rejected", "error"]
    error: Optional[str] = None


def _bearer(authorization: Optional[str]) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer device token required")
    return token


def create_app(settings: Optional[ControlPlaneSettings] = None) -> FastAPI:
    cfg = settings or ControlPlaneSettings.from_env()
    store = ControlPlaneStore(cfg.database_path)
    app = FastAPI(
        title="AI Aegis Control Plane",
        version="1.0.0",
        description="Self-hosted device enrollment and signed policy distribution.",
    )
    app.state.settings = cfg
    app.state.store = store
    app.state.local_analyzer = None

    def require_admin(x_aegis_admin_key: Optional[str] = Header(default=None)) -> None:
        if not x_aegis_admin_key or not secrets.compare_digest(
            x_aegis_admin_key, cfg.admin_key
        ):
            raise HTTPException(status_code=401, detail="Invalid admin key")

    def require_device(
        authorization: Optional[str] = Header(default=None),
        x_aegis_device_id: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        if not x_aegis_device_id:
            raise HTTPException(status_code=401, detail="Device id required")
        device = store.authenticate_device(x_aegis_device_id, _bearer(authorization))
        if device is None:
            raise HTTPException(status_code=401, detail="Invalid device credentials")
        return device

    def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> dict[str, Any]:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="API key required")
        identity = store.authenticate_api_key(x_api_key)
        if identity is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return identity

    def require_cloud_identity(
        x_api_key: Optional[str] = Header(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        """Accept the two credential forms used by existing desktop clients."""
        candidate = x_api_key
        if not candidate and authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer":
                candidate = token
        if not candidate:
            raise HTTPException(status_code=401, detail="API key required")
        identity = store.authenticate_api_key(candidate)
        if identity is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return identity

    def local_analysis(text: str) -> tuple[Any, list[dict[str, Any]], str]:
        if app.state.local_analyzer is None:
            from aegis.core.modes.local.local_mode import LocalMode
            from aegis.models.config_models import LocalModeConfig

            app.state.local_analyzer = LocalMode(LocalModeConfig())
        result = app.state.local_analyzer.analyze(text)
        matched_rules = [
            {
                "rule_id": detection.rule_id,
                "rule_name": detection.description,
                "category": detection.threat_type,
                "severity": detection.severity,
                "confidence": detection.confidence,
            }
            for detection in result.detections
        ]
        verdict = (
            "BLOCK"
            if result.is_threat and result.risk_score >= 85
            else "WARN"
            if result.is_threat
            else "ALLOW"
        )
        return result, matched_rules, verdict

    def packaged_rules(tier: str) -> list[dict[str, Any]]:
        tier_rank = {"community": 0, "professional": 1, "enterprise": 2}
        allowed_rank = tier_rank[tier]
        rules_dir = Path(__file__).resolve().parents[1] / "rules" / "community"
        collected: list[dict[str, Any]] = []
        for rule_file in sorted(rules_dir.glob("aegis_*.yml")):
            document = yaml.safe_load(rule_file.read_text(encoding="utf-8")) or {}
            for rule in document.get("rules", []):
                rule_tier = str(rule.get("tier", "community")).lower()
                if tier_rank.get(rule_tier, 0) <= allowed_rank:
                    collected.append(rule)
        return collected

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ai-aegis-control-plane"}

    @app.post(
        "/api/v1/admin/enrollment-tokens",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin)],
    )
    def create_enrollment_token(body: EnrollmentTokenRequest) -> dict[str, Any]:
        token_id = "aeti_" + secrets.token_urlsafe(10)
        token = "aet_" + secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours)
        store.create_enrollment_token(
            token_id=token_id,
            token=token,
            user_email=body.user_email,
            expires_at=expires_at.isoformat(),
        )
        return {
            "id": token_id,
            "enrollment_token": token,
            "expires_at": expires_at.isoformat(),
            "user_email": body.user_email,
        }

    @app.post(
        "/api/v1/admin/api-keys",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin)],
    )
    def create_api_key(body: ApiKeyRequest) -> dict[str, Any]:
        key_id = "aepki_" + secrets.token_urlsafe(10)
        api_key = "aepk_" + secrets.token_urlsafe(36)
        store.create_api_key(
            key_id=key_id,
            api_key=api_key,
            user_email=body.user_email,
            name=body.name,
        )
        return {
            "id": key_id,
            "api_key": api_key,
            "user_email": body.user_email,
            "name": body.name,
        }

    @app.get("/api/user/me")
    def current_user(identity: dict[str, Any] = Depends(require_cloud_identity)) -> dict[str, Any]:
        return {"id": identity["id"], "email": identity["user_email"]}

    @app.post("/analyze")
    def analyze_prompt(
        body: AnalyzeRequest, identity: dict[str, Any] = Depends(require_cloud_identity)
    ) -> dict[str, Any]:
        del identity
        result, matched_rules, verdict = local_analysis(body.prompt)
        return {
            "verdict": verdict,
            "threat_score": result.risk_score / 100,
            "confidence_score": result.confidence,
            "threat_level": (
                "critical" if result.risk_score >= 90 else "high"
                if result.risk_score >= 70 else "low"
            ),
            "matched_rules": matched_rules,
            "analysis": {
                "ml_category": matched_rules[0]["category"] if matched_rules else None
            },
            "recommendation": "Block or review the request" if result.is_threat else "Allow",
        }

    @app.post("/analyze/output")
    def analyze_output(
        body: OutputAnalyzeRequest,
        identity: dict[str, Any] = Depends(require_cloud_identity),
    ) -> dict[str, Any]:
        del identity
        started = time.perf_counter()
        result, matched_rules, verdict = local_analysis(body.output)
        detected_types = list(dict.fromkeys(rule["category"] for rule in matched_rules))
        # Only metadata is returned. The scanned model output and matched text
        # never leave this process or reappear in the response.
        detected_items = [
            {
                "type": rule["category"],
                "severity": rule["severity"],
                "rule_id": rule["rule_id"],
            }
            for rule in matched_rules
        ]
        return {
            "scan_id": "scan_" + secrets.token_urlsafe(12),
            "verdict": verdict,
            "threat_score": result.risk_score / 100,
            "confidence_score": result.confidence,
            "detected_items": detected_items,
            "detected_types": detected_types,
            "risk_level": (
                "critical" if result.risk_score >= 90 else "high"
                if result.risk_score >= 70 else "medium"
                if result.risk_score >= 40 else "low"
            ),
            "ml_status": "bundled_local_model" if body.enable_ml_validation else "disabled",
            "scan_duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "recommendations": [
                "Block or review the generated output" if result.is_threat else "Allow"
            ],
        }

    @app.post("/api/threat-analytics/")
    def threat_analytics(
        body: AnalyzeRequest,
        identity: dict[str, Any] = Depends(require_cloud_identity),
    ) -> dict[str, Any]:
        del identity
        result, matched_rules, verdict = local_analysis(body.prompt)
        return {
            "verdict": verdict,
            "is_threat": result.is_threat,
            "risk_score": result.risk_score,
            "confidence": result.confidence,
            "matched_rules": matched_rules,
            "analysis_source": "self_hosted_control_plane",
        }

    @app.post("/api/rules/sync")
    def sync_detection_rules(
        body: RulesSyncRequest,
        identity: dict[str, Any] = Depends(require_cloud_identity),
    ) -> dict[str, Any]:
        rules = packaged_rules(body.tier)
        return {
            "rules": rules,
            "total": len(rules),
            "effective_tier": body.tier,
            "subscription_tier": "enterprise",
            "included_tiers": [body.tier],
            "bundle_version": "self-hosted-1",
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "user_id": identity["id"],
            "source": "ai-aegis-control-plane",
        }

    @app.post("/api/v1/devices/enroll")
    def enroll_device(body: EnrollmentRequest) -> dict[str, Any]:
        if not body.enrollment_token.startswith("aet_"):
            raise HTTPException(
                status_code=401,
                detail={"error": "token_invalid", "message": "Invalid enrollment token"},
            )
        if store.device_by_id(body.device_id):
            raise HTTPException(
                status_code=409,
                detail={"error": "device_id_collision", "message": "Device is already enrolled"},
            )
        token_status, token_row = store.consume_enrollment_token(body.enrollment_token)
        if token_status != "ok" or token_row is None:
            error = {
                "used": "token_already_used",
                "expired": "token_expired",
            }.get(token_status, "token_invalid")
            raise HTTPException(
                status_code=401,
                detail={"error": error, "message": "Enrollment token is unavailable"},
            )
        record_id = "dev_" + secrets.token_urlsafe(12)
        user_id = "usr_" + secrets.token_urlsafe(12)
        access_token = "aedt_" + secrets.token_urlsafe(36)
        signing_key = secrets.token_urlsafe(48)
        store.create_device(
            record_id=record_id,
            device_id=body.device_id,
            user_id=user_id,
            user_email=token_row["user_email"],
            bearer_token=access_token,
            signing_key=signing_key,
        )
        return {
            "success": True,
            "device_record_id": record_id,
            "device_id": body.device_id,
            "org_id": cfg.org_id,
            "org_name": cfg.org_name,
            "user_id": user_id,
            "user_email": token_row["user_email"],
            "admin_email": cfg.admin_email,
            "group_memberships": [],
            "access_token": access_token,
            "refresh_token": None,
            "policy_bundle_signing_key": signing_key,
        }

    @app.put(
        "/api/v1/admin/policies/{policy_id}", dependencies=[Depends(require_admin)]
    )
    def publish_policy(policy_id: str, body: PolicyRequest) -> dict[str, Any]:
        if not policy_id.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=422, detail="Invalid policy id")
        return store.upsert_policy(
            policy_id=policy_id,
            name=body.name,
            mode=body.mode,
            rules=[rule.model_dump() for rule in body.rules],
        )

    @app.get("/policy/sync")
    def sync_policy(
        response: Response,
        device: dict[str, Any] = Depends(require_device),
        if_none_match: Optional[str] = Header(default=None),
    ) -> Any:
        policy = store.latest_policy()
        if policy is None:
            return Response(status_code=304)
        bundle_id = f"bnd_{policy['policy_id']}_{policy['version']}"
        if if_none_match == bundle_id:
            return Response(status_code=304)
        signed_at = datetime.now(timezone.utc)
        payload = {
            "bundle_id": bundle_id,
            "org_id": cfg.org_id,
            "policy_id": policy["policy_id"],
            "policy_name": policy["name"],
            "version": policy["version"],
            "mode": policy["mode"],
            "signed_at": signed_at.isoformat(),
            "expires_at": (signed_at + timedelta(hours=24)).isoformat(),
            "rules": policy["rules"],
        }
        payload["signature"] = sign_bundle(payload, device["signing_key"])
        response.headers["ETag"] = bundle_id
        return payload

    @app.post("/policy/applied", status_code=status.HTTP_202_ACCEPTED)
    def policy_applied(
        body: AppliedRequest, device: dict[str, Any] = Depends(require_device)
    ) -> dict[str, bool]:
        if body.device_id != device["device_id"] or body.org_id != cfg.org_id:
            raise HTTPException(status_code=403, detail="Device or organization mismatch")
        store.record_applied(body.model_dump())
        return {"accepted": True}

    @app.get(
        "/api/v1/admin/devices", dependencies=[Depends(require_admin)]
    )
    def list_devices() -> list[dict[str, Any]]:
        return store.list_devices()

    return app
