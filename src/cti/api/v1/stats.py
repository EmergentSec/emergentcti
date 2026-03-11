"""Dashboard statistics endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import verify_api_key
from cti.core.redis import cache_get, cache_set
from cti.models.api_key import ApiKey
from cti.models.feed import Feed, FeedRun, FeedRunStatus
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource

router = APIRouter()


@router.get("")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
) -> dict:
    """Dashboard stats: counts by type, feed health, recent ingestion."""
    import json

    cached = await cache_get("stats:dashboard")
    if cached:
        return json.loads(cached)

    # Total observables
    total_result = await db.execute(select(func.count(Observable.id)))
    total = total_result.scalar_one()

    # By type
    type_result = await db.execute(
        select(Observable.type, func.count(Observable.id)).group_by(Observable.type)
    )
    by_type = {row[0].value: row[1] for row in type_result.all()}

    # Feed counts
    total_feeds_result = await db.execute(select(func.count(Feed.id)))
    total_feeds = total_feeds_result.scalar_one()

    enabled_feeds_result = await db.execute(
        select(func.count(Feed.id)).where(Feed.enabled.is_(True))
    )
    feeds_enabled = enabled_feeds_result.scalar_one()

    # Last 24h ingested (only genuinely new observables)
    cutoff_24h = datetime.now(UTC) - timedelta(hours=24)
    new_24h_result = await db.execute(
        select(func.coalesce(func.sum(FeedRun.observables_new), 0)).where(
            FeedRun.completed_at >= cutoff_24h,
            FeedRun.status == FeedRunStatus.SUCCESS,
        )
    )
    last_24h_ingested = new_24h_result.scalar_one()

    # Feed health (latest run per feed)
    feeds_result = await db.execute(
        select(Feed).where(Feed.enabled.is_(True)).order_by(Feed.name)
    )
    feeds_health = []
    for feed in feeds_result.scalars():
        obs_count_result = await db.execute(
            select(func.count(ObservableSource.id)).where(ObservableSource.feed_id == feed.id)
        )
        obs_count = obs_count_result.scalar_one()

        latest_run = feed.runs[0] if feed.runs else None
        feeds_health.append(
            {
                "id": str(feed.id),
                "name": feed.name,
                "enabled": feed.enabled,
                "last_run_status": latest_run.status.value if latest_run else None,
                "last_run_at": feed.last_run_at.isoformat() if feed.last_run_at else None,
                "observable_count": obs_count,
            }
        )

    result = {
        "total_observables": total,
        "by_type": by_type,
        "total_feeds": total_feeds,
        "feeds_enabled": feeds_enabled,
        "last_24h_ingested": last_24h_ingested,
        "feeds_health": feeds_health,
    }

    try:
        await cache_set("stats:dashboard", json.dumps(result, default=str), ttl_seconds=60)
    except Exception:
        pass

    return result
