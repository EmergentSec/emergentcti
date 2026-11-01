"""Observable search, create, and detail endpoints."""
# ruff: noqa: B008, TC001, TC002, TC003

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti.api.v1.filters import parse_tag_names, parse_tlp_tokens
from cti.api.v1.reports import report_to_summary
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.redis import invalidate_observable_caches
from cti.models.observable import ObservableType
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
from cti.services import allowlist_service, observable_service, report_service, tag_service
from cti.services.allowlist_service import AllowlistMatcher
from cti.services.tlp import MarkingContext, describe_markings

router = APIRouter()


async def observables_to_responses(db: AsyncSession, observables) -> list[ObservableResponse]:
    """Serialize observables with the current allowlist and TLP state."""
    allowlist = await allowlist_service.load_matcher(db)
    markings = await describe_markings(db, observables)
    return [_obs_to_response(obs, allowlist, markings[obs.id]) for obs in observables]


async def observable_to_response(db: AsyncSession, obs) -> ObservableResponse:
    return (await observables_to_responses(db, [obs]))[0]


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
    _auth: AuthSubject = Depends(get_current_auth),
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
        page=page,
        size=size,
        sort=sort,
        order=order,
    )

    pages = (total + size - 1) // size if total > 0 else 0

    return ObservableListResponse(
        items=await observables_to_responses(db, items),
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("", response_model=ObservableResponse, status_code=201)
async def create_observable(
    data: ObservableCreate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
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
    return await observable_to_response(db, obs)


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> ObservableResponse:
    obs = await observable_service.get_observable(db, observable_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observable not found")
    return await observable_to_response(db, obs)


@router.get("/{observable_id}/reports", response_model=list[ReportSummary])
async def get_observable_reports(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[ReportSummary]:
    reports = await report_service.list_reports_for_observable(db, observable_id)
    if reports is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    return [report_to_summary(report) for report in reports]


@router.put("/{observable_id}/confidence-override", response_model=ObservableResponse)
async def set_confidence_override(
    observable_id: uuid.UUID,
    data: ConfidenceOverrideRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
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
    return await observable_to_response(db, obs)


@router.delete("/{observable_id}/confidence-override", response_model=ObservableResponse)
async def clear_confidence_override(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
    obs = await observable_service.clear_confidence_override(db, observable_id)
    if obs is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
    return await observable_to_response(db, obs)


@router.put("/{observable_id}/tlp-override", response_model=ObservableResponse)
async def set_tlp_override(
    observable_id: uuid.UUID,
    data: TlpOverrideRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
    """Reclassify an observable (may loosen or tighten). Reason required."""
    obs = await observable_service.set_tlp_override(
        db,
        observable_id,
        data.tlp,
        data.reason,
        set_by_id=auth.id if isinstance(auth, User) else None,
    )
    if obs is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
    return await observable_to_response(db, obs)


@router.delete("/{observable_id}/tlp-override", response_model=ObservableResponse)
async def clear_tlp_override(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
    obs = await observable_service.clear_tlp_override(db, observable_id)
    if obs is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
    return await observable_to_response(db, obs)


@router.put("/{observable_id}/tags", response_model=ObservableResponse)
async def set_observable_tags(
    observable_id: uuid.UUID,
    data: TagsUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ObservableResponse:
    """Replace the observable's tag set (names are normalized; new ones created)."""
    if await observable_service.get_observable(db, observable_id) is None:
        raise HTTPException(status_code=404, detail="Observable not found")
    try:
        await tag_service.set_observable_tags(db, observable_id, data.tags)
    except tag_service.TagValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await db.commit()
    # Tag filters feed blocklist cache keys and exports.
    await invalidate_observable_caches()
    obs = await observable_service.get_observable(db, observable_id)
    assert obs is not None
    return await observable_to_response(db, obs)


@router.delete("/{observable_id}", status_code=204)
async def delete_observable(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    deleted = await observable_service.delete_observable(db, observable_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Observable not found")
    await db.commit()
    await invalidate_observable_caches()
