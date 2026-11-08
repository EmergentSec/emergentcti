"""Threat-intel feed fetch and AI report generation endpoints."""
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, require_admin
from cti.models.user import User
from cti.schemas.threat_intel import (
    FeedFetchResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    ThreatIntelSkill,
    ThreatIntelSkillBody,
)
from cti.services import ai_settings_service, audit
from cti.services.ai import gateway
from cti.services.threat_intel import pipeline
from cti.services.threat_intel.feed_aggregator import FeedAggregatorError

router = APIRouter()


def _actor_user_id(auth: AuthSubject) -> object | None:
    if isinstance(auth, User):
        return auth.id
    return None


@router.get("/skills", response_model=list[ThreatIntelSkill])
async def list_skills(
    _auth: AuthSubject = Depends(require_admin),
) -> list[ThreatIntelSkill]:
    return [ThreatIntelSkill.model_validate(item) for item in pipeline.list_skills()]


@router.get("/skills/{skill_id}", response_model=ThreatIntelSkillBody)
async def get_skill(
    skill_id: str,
    _auth: AuthSubject = Depends(require_admin),
) -> ThreatIntelSkillBody:
    try:
        content = pipeline.load_skill(skill_id)
    except pipeline.ThreatIntelError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    title = content.splitlines()[0].lstrip("# ").strip() if content else skill_id
    return ThreatIntelSkillBody(id=skill_id, title=title, content=content)


@router.post("/fetch", response_model=FeedFetchResponse)
async def fetch_feeds(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(audit.audited_admin("threat_intel.fetch", "threat_intel")),
) -> FeedFetchResponse:
    actor = audit.actor_from_auth(_auth)
    try:
        result = pipeline.fetch_feeds()
    except (pipeline.ThreatIntelError, FeedAggregatorError) as exc:
        status = getattr(exc, "status_code", 500)
        message = getattr(exc, "message", str(exc))
        await audit.record_independent(
            actor=actor,
            action="threat_intel.fetch",
            resource_type="threat_intel",
            resource_id="fetch",
            outcome=audit.AuditOutcome.FAILED,
            summary={"error": message, "status": status},
            strict=False,
        )
        raise HTTPException(status_code=status if isinstance(status, int) else 500, detail=message) from exc
    audit.record(
        db,
        actor=actor,
        action="threat_intel.fetch",
        resource_type="threat_intel",
        resource_id="fetch",
        summary={"total_items": result.total_items, "summary": result.summary},
    )
    await db.commit()
    return FeedFetchResponse(
        timestamp=result.timestamp,
        total_items=result.total_items,
        summary=result.summary,
        items=result.items,
        state_file=result.state_file,
        config_path=result.config_path,
    )


@router.post("/generate-report", response_model=GenerateReportResponse)
async def generate_report(
    data: GenerateReportRequest,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(audit.audited_admin("threat_intel.generate_report", "threat_intel")),
) -> GenerateReportResponse | JSONResponse:
    actor = audit.actor_from_auth(_auth)
    try:
        result = await pipeline.generate_report_from_item(
            db,
            actor=actor,
            item=data.item,
            environment=data.environment,
            created_by_id=_actor_user_id(_auth) if isinstance(_auth, User) else None,
        )
    except ai_settings_service.AiSettingsServiceError as exc:
        await db.rollback()
        return JSONResponse(status_code=exc.status_code, content=exc.error.model_dump(mode="json"))
    except gateway.GatewayRejectionError as exc:
        await db.rollback()
        return JSONResponse(status_code=exc.status_code, content=exc.error.model_dump(mode="json"))
    except pipeline.ThreatIntelError as exc:
        await db.rollback()
        await audit.record_independent(
            actor=actor,
            action="threat_intel.generate_report",
            resource_type="threat_intel",
            resource_id="generate-report",
            outcome=audit.AuditOutcome.FAILED,
            summary={"error": exc.message, "status": exc.status_code},
            strict=False,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    audit.record(
        db,
        actor=actor,
        action="threat_intel.generate_report",
        resource_type="threat_intel",
        resource_id=result.report_id,
        summary={
            "title": result.title,
            "research_provider": result.research_provider,
            "research_model": result.research_model,
            "writer_provider": result.writer_provider,
            "writer_model": result.writer_model,
        },
    )
    await db.commit()
    return GenerateReportResponse(
        report_id=result.report_id,
        title=result.title,
        research_provider=result.research_provider,
        research_model=result.research_model,
        writer_provider=result.writer_provider,
        writer_model=result.writer_model,
        research_chars=result.research_chars,
        report_chars=result.report_chars,
    )
