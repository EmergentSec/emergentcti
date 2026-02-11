from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.feed import Feed, FeedRun, FeedRunStatus
from cti.models.observable import Observable, observable_tags
from cti.models.tag import Tag
from cti.schemas.dashboard import DashboardStats, ErroredFeed, FeedRunSummary, RecentObservable


async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    # Total observables
    total_result = await db.execute(select(func.count(Observable.id)))
    total_observables = total_result.scalar_one()

    # By type
    type_result = await db.execute(
        select(Observable.type, func.count(Observable.id)).group_by(Observable.type)
    )
    observables_by_type = {row[0].value: row[1] for row in type_result.all()}

    # Total feeds
    total_feeds_result = await db.execute(select(func.count(Feed.id)))
    total_feeds = total_feeds_result.scalar_one()

    # Active feeds
    active_result = await db.execute(
        select(func.count(Feed.id)).where(Feed.enabled.is_(True))
    )
    active_feeds = active_result.scalar_one()

    # Feeds with errors (latest run failed)
    error_result = await db.execute(
        select(func.count(func.distinct(FeedRun.feed_id))).where(
            FeedRun.status == FeedRunStatus.failure
        )
    )
    feeds_with_errors = error_result.scalar_one()

    # Errored feed details
    errored_feeds_query = (
        select(
            FeedRun.feed_id,
            Feed.name,
            FeedRun.error_message,
            FeedRun.started_at,
        )
        .join(Feed, FeedRun.feed_id == Feed.id)
        .where(FeedRun.status == FeedRunStatus.failure)
        .order_by(FeedRun.feed_id, FeedRun.started_at.desc())
    )
    errored_feeds_result = await db.execute(errored_feeds_query)
    seen_feeds: set = set()
    errored_feeds: list[ErroredFeed] = []
    for row in errored_feeds_result.all():
        if row[0] not in seen_feeds:
            seen_feeds.add(row[0])
            errored_feeds.append(
                ErroredFeed(
                    feed_id=row[0],
                    feed_name=row[1],
                    error_message=row[2],
                    last_run_at=row[3],
                )
            )

    # Observables today
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(Observable.id)).where(Observable.created_at >= today_start)
    )
    observables_today = today_result.scalar_one()

    # Recent observables
    recent_result = await db.execute(
        select(Observable).order_by(Observable.created_at.desc()).limit(10)
    )
    recent = [
        RecentObservable(
            id=obs.id,
            type=obs.type,
            value=obs.value,
            confidence_score=obs.confidence_score,
            created_at=obs.created_at,
        )
        for obs in recent_result.scalars().all()
    ]

    # Recent feed runs
    feed_runs_result = await db.execute(
        select(FeedRun, Feed.name)
        .join(Feed, FeedRun.feed_id == Feed.id)
        .order_by(FeedRun.started_at.desc())
        .limit(10)
    )
    recent_runs = [
        FeedRunSummary(
            feed_id=run.feed_id,
            feed_name=feed_name,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            observables_created=run.observables_ingested,
            observables_updated=0,
            errors=1 if run.error_message else 0,
        )
        for run, feed_name in feed_runs_result.all()
    ]

    return DashboardStats(
        total_observables=total_observables,
        observables_by_type=observables_by_type,
        total_feeds=total_feeds,
        active_feeds=active_feeds,
        feeds_with_errors=feeds_with_errors,
        observables_today=observables_today,
        recent_observables=recent,
        recent_feed_runs=recent_runs,
        errored_feeds=errored_feeds,
    )


async def get_observable_trend(db: AsyncSession, days: int = 30) -> list[dict]:
    """Daily observable creation counts for the last N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    query = (
        select(
            func.date(Observable.created_at).label("date"),
            func.count(Observable.id).label("count"),
        )
        .where(Observable.created_at >= cutoff)
        .group_by(func.date(Observable.created_at))
        .order_by(func.date(Observable.created_at))
    )
    result = await db.execute(query)
    return [{"date": str(row.date), "count": row.count} for row in result.all()]


async def get_tlp_distribution(db: AsyncSession) -> list[dict]:
    """Count of observables per TLP level."""
    query = (
        select(Observable.tlp, func.count(Observable.id).label("count"))
        .group_by(Observable.tlp)
        .order_by(func.count(Observable.id).desc())
    )
    result = await db.execute(query)
    return [{"tlp": row.tlp, "count": row.count} for row in result.all()]


async def get_top_tags(db: AsyncSession, limit: int = 15) -> list[dict]:
    """Most frequently used tags."""
    query = (
        select(Tag.name, func.count(observable_tags.c.observable_id).label("count"))
        .join(observable_tags, Tag.id == observable_tags.c.tag_id)
        .group_by(Tag.name)
        .order_by(func.count(observable_tags.c.observable_id).desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return [{"tag": row.name, "count": row.count} for row in result.all()]
