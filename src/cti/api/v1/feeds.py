"""Feed CRUD, trigger, and run history endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.schemas.feed import FeedCreate, FeedResponse, FeedRunResponse, FeedUpdate
from cti.services import feed_service

router = APIRouter()


def _feed_to_response(feed, observable_count: int = 0) -> FeedResponse:
    latest_run = None
    if feed.runs:
        r = feed.runs[0]
        latest_run = FeedRunResponse(
            id=r.id,
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            observables_ingested=r.observables_ingested,
            observables_new=r.observables_new,
            error_message=r.error_message,
        )

    return FeedResponse(
        id=feed.id,
        name=feed.name,
        description=feed.description,
        feed_type=feed.feed_type,
        url=feed.url,
        config=feed.config,
        schedule_cron=feed.schedule_cron,
        enabled=feed.enabled,
        is_preconfigured=feed.is_preconfigured,
        default_confidence=feed.default_confidence,
        last_run_at=feed.last_run_at,
        observable_count=observable_count,
        latest_run=latest_run,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


@router.get("", response_model=list[FeedResponse])
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[FeedResponse]:
    feeds = await feed_service.list_feeds(db)
    result = []
    for feed in feeds:
        count = await feed_service.get_observable_count_for_feed(db, feed.id)
        result.append(_feed_to_response(feed, observable_count=count))
    return result


@router.post("", response_model=FeedResponse, status_code=201)
async def create_feed(
    data: FeedCreate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> FeedResponse:
    feed = await feed_service.create_feed(db, data.model_dump())
    await db.commit()

    # Sync scheduler if feed is enabled with a schedule
    if feed.enabled and feed.schedule_cron:
        from cti.services.scheduler import sync_feed_jobs
        await sync_feed_jobs(db)

    return _feed_to_response(feed)


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> FeedResponse:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    count = await feed_service.get_observable_count_for_feed(db, feed.id)
    return _feed_to_response(feed, observable_count=count)


@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: uuid.UUID,
    data: FeedUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> FeedResponse:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    feed = await feed_service.update_feed(
        db, feed, data.model_dump(exclude_unset=True)
    )
    await db.commit()

    # Sync scheduler after feed update
    from cti.services.scheduler import sync_feed_jobs
    await sync_feed_jobs(db)

    count = await feed_service.get_observable_count_for_feed(db, feed.id)
    return _feed_to_response(feed, observable_count=count)


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    deleted = await feed_service.delete_feed(db, feed)
    if not deleted:
        raise HTTPException(
            status_code=400, detail="Cannot delete pre-configured feeds. Disable them instead."
        )
    await db.commit()

    from cti.services.scheduler import sync_feed_jobs
    await sync_feed_jobs(db)


@router.post("/{feed_id}/trigger", response_model=FeedRunResponse)
async def trigger_feed(
    feed_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> FeedRunResponse:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    if not feed.enabled:
        raise HTTPException(status_code=400, detail="Feed is not enabled")

    run = await feed_service.create_feed_run(db, feed.id)
    await db.commit()

    # Run in background so API responds immediately
    async def _bg_run() -> None:
        from cti.core.database import async_session_factory
        from cti.feeds.runner import run_feed
        async with async_session_factory() as bg_db:
            await run_feed(feed_id, bg_db, run_id=run.id)

    background_tasks.add_task(_bg_run)

    return FeedRunResponse(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        observables_ingested=run.observables_ingested,
        observables_new=run.observables_new,
        error_message=run.error_message,
    )


@router.get("/{feed_id}/runs", response_model=list[FeedRunResponse])
async def get_feed_runs(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[FeedRunResponse]:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    runs = await feed_service.get_feed_runs(db, feed.id)
    return [
        FeedRunResponse(
            id=r.id,
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            observables_ingested=r.observables_ingested,
            observables_new=r.observables_new,
            error_message=r.error_message,
        )
        for r in runs
    ]
