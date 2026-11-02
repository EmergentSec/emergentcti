"""Observable search, create, and detail endpoints."""
# ruff: noqa: B008, TC001, TC002, TC003

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cti.api.v1.filters import parse_tag_names, parse_tlp_tokens
from cti.api.v1.reports import report_to_summary
from cti.api.v1.tlp_guard import ensure_observable_visible
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.redis import invalidate_observable_caches
from cti.models.observable import ObservableType
from cti.models.tlp import Tlp
from cti.models.user import User
from cti.schemas.observable import (
    ConfidenceOverrideRequest,
    ConfidenceOverrideResponse,
    ObservableCreate,
    ObservableListResponse,
    ObservableResponse,
    ObservableSourceResponse,
    TagsUpdate,
    TlpOverrideRequest,
    TlpOverrideResponse,
    TlpSource,
)
from cti.schemas.report import ReportSummary
from cti.services import allowlist_service, audit, observable_service, report_service, tag_service
from cti.services.allowlist_service import AllowlistMatcher
from cti.services.tlp import (
    MarkingContext,
    MarkingInput,
    describe_markings,
    hide_red_for,
    is_red_observable,
)

router = APIRouter()

_RESTRICTED_REPORT = "Restricted report"


async def _record_observable_failure(
    db: AsyncSession,
    *,
    actor: audit.Actor,
    action: str,
    resource_id: uuid.UUID,
    status: int,
    reason: str,
    resource_label: object = None,
    outcome: audit.AuditOutcome = audit.AuditOutcome.FAILED,
) -> None:
    await db.rollback()
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type="observable",
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=outcome,
        summary={"reason": reason, "status": status},
        strict=False,
    )


def _redact_red_reports(marking: MarkingContext) -> MarkingContext:
    """For API-key callers: keep a RED report's restriction, not its identity."""
    return MarkingContext(
        marking.effective,
        [
            MarkingInput("report", None, _RESTRICTED_REPORT, src.tlp)
            if src.kind == "report" and src.tlp is Tlp.RED
            else src
            for src in marking.sources
        ],
    )


async def observables_to_responses(
    db: AsyncSession, observables, auth: object = None
) -> list[ObservableResponse]:
    """Serialize observables with the current allowlist and TLP state."""
    allowlist = await allowlist_service.load_matcher(db)
    markings = await describe_markings(db, observables)
    if hide_red_for(auth):
        markings = {k: _redact_red_reports(v) for k, v in markings.items()}
    return [_obs_to_response(obs, allowlist, markings[obs.id]) for obs in observables]


async def observable_to_response(db: AsyncSession, obs, auth: object = None) -> ObservableResponse:
    return (await observables_to_responses(db, [obs], auth))[0]


async def _mutation_response(db: AsyncSession, obs, auth: object) -> ObservableResponse | Response:
    """Response after a successful change.

    If an API key's change left the observable RED (e.g. it set a RED
    override), the change stands but the RED item is not echoed back: 204.
    """
    if hide_red_for(auth) and await is_red_observable(db, obs.id):
        return Response(status_code=204)
    return await observable_to_response(db, obs, auth)


def _obs_to_response(
    obs, allowlist: AllowlistMatcher, marking: MarkingContext
) -> ObservableResponse:
    entry_ids = allowlist.match(obs.type, obs.value)
    return ObservableResponse(
        id=obs.id,
        type=obs.type,
        value=obs.value,
        confidence_score=obs.confidence_score,
        manual_confidence=obs.manual_confidence,
        confidence_override=(
            ConfidenceOverrideResponse(
                value=obs.confidence_override,
                set_at=obs.override_set_at,
                set_by=(obs.override_set_by.username if obs.override_set_by is not None else None),
            )
            if obs.confidence_override is not None and obs.override_set_at is not None
            else None
        ),
        first_seen=obs.first_seen,
        last_seen=obs.last_seen,
        source_count=len(obs.sources),
        sources=[
            ObservableSourceResponse(
                feed_id=s.feed_id,
                feed_name=s.feed.name if s.feed else "Unknown",
                source_confidence=s.source_confidence,
                native_confidence=s.native_confidence,
                first_seen_by_feed=s.first_seen_by_feed,
                last_seen_by_feed=s.last_seen_by_feed,
            )
            for s in obs.sources
        ],
        allowlisted=bool(entry_ids),
        allowlist_entry_ids=entry_ids,
        tags=sorted(tag.name for tag in obs.tags),
        manual_tlp=obs.manual_tlp,
        effective_tlp=marking.effective,
        tlp_sources=[
            TlpSource(kind=src.kind, id=src.id, name=src.name, tlp=src.tlp)
            for src in marking.sources
        ],
        tlp_override=(
            TlpOverrideResponse(
                tlp=obs.tlp_override,
                reason=obs.tlp_override_reason or "",
                set_at=obs.tlp_override_set_at,
                set_by=(
                    obs.tlp_override_set_by.username
                    if obs.tlp_override_set_by is not None
                    else None
                ),
            )
            if obs.tlp_override is not None and obs.tlp_override_set_at is not None
            else None
        ),
        created_at=obs.created_at,
        updated_at=obs.updated_at,
    )


@router.get("", response_model=ObservableListResponse)
async def list_observables(
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
    q: str | None = None,
    type: ObservableType | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    source: str | None = Query(default=None, description="Feed UUID or 'manual'"),
    last_seen_after: datetime | None = None,
    tag: list[str] | None = Query(default=None, description="Match ANY listed tag"),
    tlp: list[str] | None = Query(
        default=None, description="Effective marking or 'unspecified'; match ANY"
    ),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="last_seen"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> ObservableListResponse:
    # Parse source filter: UUID string → feed_id, "manual" → manual_only
    feed_id: uuid.UUID | None = None
    manual_only = False
    if source == "manual":
        manual_only = True
    elif source:
        try:
            feed_id = uuid.UUID(source)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="source must be a feed UUID or 'manual'",
            ) from None

    items, total = await observable_service.get_observables(
        db,
        q=q,
        obs_type=type,
        confidence_min=confidence_min,
        feed_id=feed_id,
        manual_only=manual_only,
        last_seen_after=last_seen_after,
        tags=parse_tag_names(tag),
        tlp=parse_tlp_tokens(tlp),
        exclude_red=hide_red_for(auth),
        page=page,
        size=size,
        sort=sort,
        order=order,
    )

    pages = (total + size - 1) // size if total > 0 else 0

    return ObservableListResponse(
        items=await observables_to_responses(db, items, auth),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("", response_model=ObservableResponse, status_code=201)
async def create_observable(
    data: ObservableCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse | Response:
    existing_id = await observable_service.find_observable_id(db, data.type, data.value)
    if existing_id is not None:
        # An API key cannot upsert (and so read back) an existing RED observable.
        await ensure_observable_visible(db, auth, existing_id)
    obs, _created = await observable_service.create_observable(
        db,
        obs_type=data.type,
        value=data.value,
        confidence_score=data.confidence_score,
        tlp=data.tlp,
    )
    await db.commit()
    # Even an upsert of an existing value can raise its confidence (MAX), which
    # changes blocklist eligibility, so invalidate on every successful create.
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
) -> ObservableResponse:
    await ensure_observable_visible(db, auth, observable_id)
    obs = await observable_service.get_observable(db, observable_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observable not found")
    return await observable_to_response(db, obs, auth)


@router.get("/{observable_id}/reports", response_model=list[ReportSummary])
async def get_observable_reports(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
) -> list[ReportSummary]:
    await ensure_observable_visible(db, auth, observable_id)
    reports = await report_service.list_reports_for_observable(db, observable_id)
    if reports is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    if hide_red_for(auth):
        reports = [r for r in reports if r.tlp != Tlp.RED.value]
    return [report_to_summary(report) for report in reports]


@router.put("/{observable_id}/confidence-override", response_model=ObservableResponse)
async def set_confidence_override(
    observable_id: uuid.UUID,
    data: ConfidenceOverrideRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse | Response:
    await ensure_observable_visible(db, auth, observable_id)
    obs = await observable_service.set_confidence_override(
        db,
        observable_id,
        data.confidence,
        set_by_id=auth.id if isinstance(auth, User) else None,
    )
    if obs is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.delete("/{observable_id}/confidence-override", response_model=ObservableResponse)
async def clear_confidence_override(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse | Response:
    await ensure_observable_visible(db, auth, observable_id)
    obs = await observable_service.clear_confidence_override(db, observable_id)
    if obs is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.put("/{observable_id}/tlp-override", response_model=ObservableResponse)
async def set_tlp_override(
    observable_id: uuid.UUID,
    data: TlpOverrideRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin(
            "observable.tlp_override_set", "observable", resource_id_param="observable_id"
        )
    ),
) -> ObservableResponse | Response:
    """Reclassify an observable (may loosen or tighten). Reason required."""
    actor = audit.actor_from_auth(auth)
    if hide_red_for(auth) and await is_red_observable(db, observable_id):
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_set",
            resource_id=observable_id,
            status=404,
            reason="red_restricted",
            outcome=audit.AuditOutcome.DENIED,
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    try:
        await ensure_observable_visible(db, auth, observable_id)
    except HTTPException as exc:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_set",
            resource_id=observable_id,
            status=exc.status_code,
            reason="not_found",
        )
        raise
    current = await observable_service.get_observable(db, observable_id)
    if current is None:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_set",
            resource_id=observable_id,
            status=404,
            reason="not_found",
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    before = current.tlp_override
    obs = await observable_service.set_tlp_override(
        db,
        observable_id,
        data.tlp,
        data.reason,
        set_by_id=auth.id if isinstance(auth, User) else None,
    )
    if obs is None:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_set",
            resource_id=observable_id,
            status=404,
            reason="not_found",
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    audit.record(
        db,
        actor=actor,
        action="observable.tlp_override_set",
        resource_type="observable",
        resource_id=obs.id,
        resource_label=obs.value,
        summary={
            "before": before,
            "after": obs.tlp_override,
            "reason_present": bool(data.reason),
            "reason_length": len(data.reason),
        },
    )
    await db.commit()
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.delete("/{observable_id}/tlp-override", response_model=ObservableResponse)
async def clear_tlp_override(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin(
            "observable.tlp_override_clear", "observable", resource_id_param="observable_id"
        )
    ),
) -> ObservableResponse | Response:
    actor = audit.actor_from_auth(auth)
    if hide_red_for(auth) and await is_red_observable(db, observable_id):
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_clear",
            resource_id=observable_id,
            status=404,
            reason="red_restricted",
            outcome=audit.AuditOutcome.DENIED,
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    try:
        await ensure_observable_visible(db, auth, observable_id)
    except HTTPException as exc:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_clear",
            resource_id=observable_id,
            status=exc.status_code,
            reason="not_found",
        )
        raise
    current = await observable_service.get_observable(db, observable_id)
    if current is None:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_clear",
            resource_id=observable_id,
            status=404,
            reason="not_found",
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    before = current.tlp_override
    obs = await observable_service.clear_tlp_override(db, observable_id)
    if obs is None:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tlp_override_clear",
            resource_id=observable_id,
            status=404,
            reason="not_found",
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    audit.record(
        db,
        actor=actor,
        action="observable.tlp_override_clear",
        resource_type="observable",
        resource_id=obs.id,
        resource_label=obs.value,
        summary={"before": before, "after": None},
    )
    await db.commit()
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.put("/{observable_id}/tags", response_model=ObservableResponse)
async def set_observable_tags(
    observable_id: uuid.UUID,
    data: TagsUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin(
            "observable.tags_update", "observable", resource_id_param="observable_id"
        )
    ),
) -> ObservableResponse | Response:
    """Replace the observable's tag set (names are normalized; new ones created)."""
    actor = audit.actor_from_auth(auth)
    if hide_red_for(auth) and await is_red_observable(db, observable_id):
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tags_update",
            resource_id=observable_id,
            status=404,
            reason="red_restricted",
            outcome=audit.AuditOutcome.DENIED,
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    try:
        await ensure_observable_visible(db, auth, observable_id)
    except HTTPException as exc:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tags_update",
            resource_id=observable_id,
            status=exc.status_code,
            reason="not_found",
        )
        raise
    current = await observable_service.get_observable(db, observable_id)
    if current is None:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tags_update",
            resource_id=observable_id,
            status=404,
            reason="not_found",
        )
        raise HTTPException(status_code=404, detail="Observable not found")
    before = {tag.name for tag in current.tags}
    try:
        await tag_service.set_observable_tags(db, observable_id, data.tags)
    except tag_service.TagValidationError as exc:
        await _record_observable_failure(
            db,
            actor=actor,
            action="observable.tags_update",
            resource_id=observable_id,
            resource_label=current.value,
            status=422,
            reason="invalid_tags",
        )
        raise HTTPException(status_code=422, detail=str(exc)) from None
    obs = await observable_service.get_observable(db, observable_id)
    assert obs is not None
    after = {tag.name for tag in obs.tags}
    audit.record(
        db,
        actor=actor,
        action="observable.tags_update",
        resource_type="observable",
        resource_id=obs.id,
        resource_label=obs.value,
        summary={"added": sorted(after - before), "removed": sorted(before - after)},
    )
    await db.commit()
    # Tag filters feed blocklist cache keys and exports.
    await invalidate_observable_caches()
    return await _mutation_response(db, obs, auth)


@router.delete("/{observable_id}", status_code=204)
async def delete_observable(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> None:
    await ensure_observable_visible(db, auth, observable_id)
    deleted = await observable_service.delete_observable(db, observable_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
