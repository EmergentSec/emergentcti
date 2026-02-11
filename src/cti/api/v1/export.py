"""Export API routes for STIX 2.1, CSV, and JSON formats."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cti.core.database import get_db
from cti.core.dependencies import CurrentUser
from cti.models.observable import Observable, ObservableType, observable_sources, observable_tags
from cti.models.relationship import ObservableRelationship
from cti.models.tag import Tag
from cti.services import export_service, observable_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_filtered_observables(
    db: AsyncSession,
    type: ObservableType | None = None,
    value: str | None = None,
    confidence_min: int | None = None,
    tlp: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    feed_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 1000,
) -> list[Observable]:
    """Fetch observables with filters, reusing the same filter logic as list_observables."""
    query = select(Observable)

    if feed_id:
        query = query.join(observable_sources).where(observable_sources.c.feed_id == feed_id)

    if type:
        query = query.where(Observable.type == type)

    if value:
        query = query.where(Observable.value.ilike(f"%{value}%"))

    if confidence_min is not None:
        query = query.where(Observable.confidence_score >= confidence_min)

    if tlp:
        query = query.where(Observable.tlp == tlp)

    if category:
        query = query.where(Observable.category == category)

    if tag:
        query = query.join(observable_tags).join(Tag).where(Tag.name == tag)

    query = query.order_by(Observable.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _get_relationships_for_observables(
    db: AsyncSession,
    observable_ids: list[uuid.UUID],
) -> list[ObservableRelationship]:
    """Fetch all relationships where both source and target are in the given ID set."""
    if not observable_ids:
        return []

    query = (
        select(ObservableRelationship)
        .options(
            joinedload(ObservableRelationship.source),
            joinedload(ObservableRelationship.target),
        )
        .where(
            ObservableRelationship.source_id.in_(observable_ids),
            ObservableRelationship.target_id.in_(observable_ids),
        )
    )
    result = await db.execute(query)
    return list(result.unique().scalars().all())


@router.get("/stix")
async def export_stix(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    type: ObservableType | None = None,
    value: str | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    tlp: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    feed_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> JSONResponse:
    """Export filtered observables as a STIX 2.1 Bundle (JSON)."""
    observables = await _get_filtered_observables(
        db,
        type=type,
        value=value,
        confidence_min=confidence_min,
        tlp=tlp,
        category=category,
        tag=tag,
        feed_id=feed_id,
        skip=skip,
        limit=limit,
    )

    obs_ids = [obs.id for obs in observables]
    relationships = await _get_relationships_for_observables(db, obs_ids)

    bundle = export_service.export_stix_bundle(observables, relationships)
    return JSONResponse(
        content=bundle,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cti-export.stix.json"},
    )


@router.get("/csv")
async def export_csv(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    type: ObservableType | None = None,
    value: str | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    tlp: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    feed_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> StreamingResponse:
    """Export filtered observables as CSV."""
    observables = await _get_filtered_observables(
        db,
        type=type,
        value=value,
        confidence_min=confidence_min,
        tlp=tlp,
        category=category,
        tag=tag,
        feed_id=feed_id,
        skip=skip,
        limit=limit,
    )

    csv_content = export_service.export_csv(observables)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cti-export.csv"},
    )


@router.get("/json")
async def export_json(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    type: ObservableType | None = None,
    value: str | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    tlp: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    feed_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> StreamingResponse:
    """Export filtered observables as JSON."""
    observables = await _get_filtered_observables(
        db,
        type=type,
        value=value,
        confidence_min=confidence_min,
        tlp=tlp,
        category=category,
        tag=tag,
        feed_id=feed_id,
        skip=skip,
        limit=limit,
    )

    json_content = export_service.export_json(observables)

    return StreamingResponse(
        iter([json_content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cti-export.json"},
    )


@router.get("/observables/{observable_id}/stix")
async def export_observable_stix(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Export a single observable as a STIX 2.1 object."""
    observable = await observable_service.get_observable(db, observable_id)
    if not observable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observable not found",
        )

    bundle = export_service.export_stix_bundle([observable])
    return JSONResponse(
        content=bundle,
        media_type="application/json",
    )


@router.post("/selected")
async def export_selected(
    body: dict,
    _current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export selected observables by IDs in STIX, CSV, or JSON format."""
    ids = [uuid.UUID(i) for i in body.get("ids", [])]
    fmt = body.get("format", "json")

    # Load observables by IDs
    result = await db.execute(select(Observable).where(Observable.id.in_(ids)))
    observables = list(result.scalars().all())

    if fmt == "stix":
        obs_ids = [obs.id for obs in observables]
        relationships = await _get_relationships_for_observables(db, obs_ids)
        bundle = export_service.export_stix_bundle(observables, relationships)
        return JSONResponse(
            content=bundle,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=cti-export.stix.json"},
        )
    elif fmt == "csv":
        csv_content = export_service.export_csv(observables)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )
    else:
        json_content = export_service.export_json(observables)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=export.json"},
        )
