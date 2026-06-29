"""Observable search, create, and detail endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate, ObservableListResponse, ObservableResponse, ObservableSourceResponse
from cti.services import observable_service

router = APIRouter()


def _obs_to_response(obs) -> ObservableResponse:
    return ObservableResponse(
        id=obs.id,
        type=obs.type,
        value=obs.value,
        confidence_score=obs.confidence_score,
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
            raise HTTPException(status_code=400, detail="source must be a feed UUID or 'manual'")

    items, total = await observable_service.get_observables(
        db,
        q=q,
        obs_type=type,
        confidence_min=confidence_min,
        feed_id=feed_id,
        manual_only=manual_only,
        last_seen_after=last_seen_after,
        page=page,
        size=size,
        sort=sort,
        order=order,
    )

    pages = (total + size - 1) // size if total > 0 else 0

    return ObservableListResponse(
        items=[_obs_to_response(obs) for obs in items],
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
    )
    await db.commit()
    return _obs_to_response(obs)


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> ObservableResponse:
    obs = await observable_service.get_observable(db, observable_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observable not found")
    return _obs_to_response(obs)


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
