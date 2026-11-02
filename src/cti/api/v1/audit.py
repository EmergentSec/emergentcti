"""Admin-only, read-only audit history API.

There are deliberately no POST/PUT/PATCH/DELETE routes: history is append-only
through the application. Only the retention job deletes events.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, require_admin
from cti.schemas.audit import AuditEventPage, AuditEventResponse, AuditMetaResponse
from cti.services import audit
from cti.services.audit import ActorType, AuditOutcome

router = APIRouter()


@router.get("/events", response_model=AuditEventPage)
async def list_audit_events(
    since: datetime | None = Query(None, description="Inclusive lower bound (ISO 8601)"),
    until: datetime | None = Query(None, description="Exclusive upper bound (ISO 8601)"),
    actor_type: ActorType | None = None,
    actor_id: str | None = Query(None, max_length=64),
    action: list[str] | None = Query(None, description="Repeatable; exact match"),
    resource_type: str | None = Query(None, max_length=32),
    resource_id: str | None = Query(None, max_length=64),
    outcome: list[AuditOutcome] | None = Query(None, description="Repeatable"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AuditEventPage:
    items, total = await audit.list_events(
        db,
        since=since,
        until=until,
        actor_type=actor_type,
        actor_id=actor_id,
        actions=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcomes=outcome,
        page=page,
        size=size,
    )
    return AuditEventPage(
        items=[AuditEventResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.get("/meta", response_model=AuditMetaResponse)
async def audit_meta(_auth: AuthSubject = Depends(require_admin)) -> AuditMetaResponse:
    return AuditMetaResponse(
        actions=list(audit.ACTION_CATALOG),
        actor_types=[t.value for t in ActorType],
        outcomes=[o.value for o in AuditOutcome],
        resource_types=sorted(set(audit.ACTION_CATALOG.values())),
        retention_days=get_settings().AUDIT_RETENTION_DAYS,
    )
