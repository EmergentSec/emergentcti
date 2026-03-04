"""Feed CRUD operations and default feed seeding."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.feeds.defaults import DEFAULT_FEEDS
from cti.models.feed import Feed, FeedRun, FeedRunStatus, FeedType
from cti.models.observable_source import ObservableSource

logger = logging.getLogger(__name__)


async def list_feeds(db: AsyncSession) -> list[Feed]:
    """List all feeds ordered by name, with latest run info eagerly loaded."""
    result = await db.execute(select(Feed).order_by(Feed.name))
    return list(result.scalars().all())


async def get_feed(db: AsyncSession, feed_id: uuid.UUID) -> Feed | None:
    """Get a single feed by ID."""
    result = await db.execute(select(Feed).where(Feed.id == feed_id))
    return result.scalar_one_or_none()


async def create_feed(db: AsyncSession, data: dict) -> Feed:
    """Create a custom feed.

    If ``data`` contains an ``auth_config`` key it is encrypted and stored
    separately from the plain-text columns.
    """
    auth_config = data.pop("auth_config", None)
    feed = Feed(**data, is_preconfigured=False)
    if auth_config:
        feed.auth_config_encrypted = encrypt_config(auth_config)
    db.add(feed)
    await db.flush()
    return feed


async def update_feed(db: AsyncSession, feed: Feed, data: dict) -> Feed:
    """Update a feed.

    For preconfigured feeds only ``enabled``, ``schedule_cron``,
    ``default_confidence``, and ``auth_config`` may be modified.
    """
    auth_config = data.pop("auth_config", None)

    if feed.is_preconfigured:
        allowed = {"enabled", "schedule_cron", "default_confidence", "auth_config"}
        data = {k: v for k, v in data.items() if k in allowed and v is not None}

    for key, value in data.items():
        if value is not None:
            setattr(feed, key, value)

    if auth_config:
        feed.auth_config_encrypted = encrypt_config(auth_config)

    await db.flush()
    return feed


async def delete_feed(db: AsyncSession, feed: Feed) -> bool:
    """Delete a custom feed.

    Returns ``False`` (and does nothing) if the feed is preconfigured.
    """
    if feed.is_preconfigured:
        return False
    await db.delete(feed)
    await db.flush()
    return True


async def create_feed_run(db: AsyncSession, feed_id: uuid.UUID) -> FeedRun:
    """Create a new feed-run record in *running* status."""
    run = FeedRun(feed_id=feed_id)
    db.add(run)
    await db.flush()
    return run


async def complete_feed_run(
    db: AsyncSession,
    run: FeedRun,
    status: FeedRunStatus,
    observables_ingested: int = 0,
    observables_new: int = 0,
    error_message: str | None = None,
) -> FeedRun:
    """Mark a feed run as completed (success or failure)."""
    run.status = status
    run.completed_at = datetime.now(UTC)
    run.observables_ingested = observables_ingested
    run.observables_new = observables_new
    run.error_message = error_message
    await db.flush()
    return run


async def get_feed_runs(
    db: AsyncSession, feed_id: uuid.UUID, limit: int = 20
) -> list[FeedRun]:
    """Return recent feed runs for a given feed, newest first."""
    result = await db.execute(
        select(FeedRun)
        .where(FeedRun.feed_id == feed_id)
        .order_by(FeedRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_observable_count_for_feed(
    db: AsyncSession, feed_id: uuid.UUID
) -> int:
    """Count distinct observables contributed by this feed."""
    result = await db.execute(
        select(func.count(ObservableSource.id)).where(
            ObservableSource.feed_id == feed_id
        )
    )
    return result.scalar_one()


async def seed_default_feeds(db: AsyncSession) -> int:
    """Seed pre-configured feeds if they don't already exist.

    Returns the number of newly created feeds.
    """
    existing = await db.execute(
        select(Feed.name).where(Feed.is_preconfigured.is_(True))
    )
    existing_names: set[str] = {row[0] for row in existing.all()}

    count = 0
    for feed_def in DEFAULT_FEEDS:
        if feed_def["name"] in existing_names:
            continue

        feed = Feed(
            name=feed_def["name"],
            feed_type=feed_def["feed_type"],
            url=feed_def.get("url"),
            config=feed_def.get("config"),
            schedule_cron=feed_def.get("schedule_cron"),
            default_confidence=feed_def.get("default_confidence", 50),
            enabled=False,  # user must explicitly enable
            is_preconfigured=True,
        )
        db.add(feed)
        count += 1

    if count:
        await db.flush()
        logger.info("Seeded %d default feeds", count)

    return count


async def list_enabled_feeds_with_schedule(db: AsyncSession) -> list[Feed]:
    """Get all enabled feeds that have a cron schedule configured."""
    result = await db.execute(
        select(Feed).where(
            Feed.enabled.is_(True),
            Feed.schedule_cron.isnot(None),
        )
    )
    return list(result.scalars().all())
