"""Blocklist and JSON export endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import verify_api_key
from cti.core.redis import cache_get, cache_set
from cti.models.api_key import ApiKey
from cti.models.observable import ObservableType
from cti.schemas.export import ExportObservable, JsonExportResponse
from cti.services import observable_service

router = APIRouter()


@router.get("/blocklist/{obs_type}", response_class=PlainTextResponse)
async def get_blocklist(
    obs_type: ObservableType,
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
    confidence_min: int = Query(default=70, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1),
    feed_id: uuid.UUID | None = None,
) -> PlainTextResponse:
    """Plain text blocklist — one IOC per line. For FW/EDL integration."""
    cache_key = f"blocklist:{obs_type.value}:{confidence_min}:{max_age_days}:{feed_id}"

    cached = await cache_get(cache_key)
    if cached is not None:
        count = cached.count("\n") + 1 if cached else 0
        return PlainTextResponse(
            content=cached,
            media_type="text/plain",
            headers={"X-Observable-Count": str(count), "X-Cache": "HIT"},
        )

    values = await observable_service.get_blocklist(
        db,
        obs_type=obs_type,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        feed_id=feed_id,
    )

    text = "\n".join(values)

    try:
        await cache_set(cache_key, text, ttl_seconds=300)
    except Exception:
        pass  # Cache failure is non-fatal

    return PlainTextResponse(
        content=text,
        media_type="text/plain",
        headers={"X-Observable-Count": str(len(values)), "X-Cache": "MISS"},
    )


@router.get("/json")
async def export_json(
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
    type: ObservableType | None = None,
    confidence_min: int = Query(default=0, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1),
    feed_id: uuid.UUID | None = None,
    limit: int = Query(default=10000, ge=1, le=100000),
) -> JsonExportResponse:
    """JSON export with filters."""
    observables = await observable_service.get_export_json(
        db,
        obs_type=type,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        feed_id=feed_id,
        limit=limit,
    )

    filters: dict = {}
    if type:
        filters["type"] = type.value
    if confidence_min:
        filters["confidence_min"] = confidence_min
    if max_age_days:
        filters["max_age_days"] = max_age_days

    return JsonExportResponse(
        exported_at=datetime.now(UTC),
        count=len(observables),
        filters=filters,
        observables=[
            ExportObservable(
                type=obs.type,
                value=obs.value,
                confidence_score=obs.confidence_score,
                last_seen=obs.last_seen,
                sources=[s.feed.name for s in obs.sources if s.feed],
            )
            for obs in observables
        ],
    )


@router.get("/text", response_class=PlainTextResponse)
async def export_text(
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
    confidence_min: int = Query(default=0, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1),
) -> PlainTextResponse:
    """Plain text export — all types mixed, one per line."""
    observables = await observable_service.get_export_json(
        db,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        limit=100000,
    )
    text = "\n".join(obs.value for obs in observables)
    return PlainTextResponse(
        content=text,
        media_type="text/plain",
        headers={"X-Observable-Count": str(len(observables))},
    )
