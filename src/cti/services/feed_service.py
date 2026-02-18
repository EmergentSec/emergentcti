import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.models.feed import Feed, FeedRun, FeedRunStatus
from cti.schemas.feed import FeedCreate, FeedUpdate


async def create_feed(db: AsyncSession, data: FeedCreate) -> Feed:
    auth_encrypted = None
    if data.auth_config:
        auth_encrypted = encrypt_config(json.dumps(data.auth_config))

    feed = Feed(
        name=data.name,
        description=data.description,
        feed_type=data.feed_type,
        url=data.url,
        config=data.config,
        schedule_cron=data.schedule_cron,
        enabled=data.enabled,
        auth_config_encrypted=auth_encrypted,
        default_ttl_days=data.default_ttl_days,
    )
    db.add(feed)
    await db.flush()
    await db.refresh(feed)
    return feed


async def get_feed(db: AsyncSession, feed_id: uuid.UUID) -> Feed | None:
    result = await db.execute(select(Feed).where(Feed.id == feed_id))
    return result.scalar_one_or_none()


async def list_feeds(db: AsyncSession) -> list[Feed]:
    result = await db.execute(select(Feed).order_by(Feed.name))
    return list(result.scalars().all())


async def update_feed(db: AsyncSession, feed_id: uuid.UUID, data: FeedUpdate) -> Feed | None:
    feed = await get_feed(db, feed_id)
    if not feed:
        return None

    update_data = data.model_dump(exclude_unset=True)
    auth_config = update_data.pop("auth_config", None)

    for field, value in update_data.items():
        setattr(feed, field, value)

    if auth_config is not None:
        feed.auth_config_encrypted = encrypt_config(json.dumps(auth_config))

    await db.flush()
    await db.refresh(feed)
    return feed


async def delete_feed(db: AsyncSession, feed_id: uuid.UUID) -> bool:
    feed = await get_feed(db, feed_id)
    if not feed:
        return False
    await db.delete(feed)
    await db.flush()
    return True


def get_feed_auth_config(feed: Feed) -> dict | None:
    if feed.auth_config_encrypted:
        return json.loads(decrypt_config(feed.auth_config_encrypted))
    return None


async def create_feed_run(db: AsyncSession, feed_id: uuid.UUID) -> FeedRun:
    run = FeedRun(feed_id=feed_id, status=FeedRunStatus.running)
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


async def update_feed_run(
    db: AsyncSession,
    run: FeedRun,
    status: FeedRunStatus,
    observables_ingested: int = 0,
    error_message: str | None = None,
) -> FeedRun:
    from datetime import UTC, datetime

    run.status = status
    run.observables_ingested = observables_ingested
    run.error_message = error_message
    run.completed_at = datetime.now(UTC)
    await db.flush()
    return run


async def get_feed_runs(
    db: AsyncSession, feed_id: uuid.UUID, limit: int = 20
) -> list[FeedRun]:
    result = await db.execute(
        select(FeedRun)
        .where(FeedRun.feed_id == feed_id)
        .order_by(FeedRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def bulk_update_feeds(
    db: AsyncSession, ids: list[uuid.UUID], enabled: bool | None = None
) -> int:
    from sqlalchemy import update as sa_update

    if enabled is None:
        return 0
    result = await db.execute(
        sa_update(Feed).where(Feed.id.in_(ids)).values(enabled=enabled)
    )
    await db.flush()
    return result.rowcount


async def bulk_delete_feeds(db: AsyncSession, ids: list[uuid.UUID]) -> int:
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        sa_delete(Feed).where(Feed.id.in_(ids))
    )
    await db.flush()
    return result.rowcount


async def seed_default_feeds(db: AsyncSession) -> int:
    """Seed default feed configurations if they don't already exist.

    Returns the number of feeds created.
    """
    import logging
    import os

    from cti.feeds.defaults import DEFAULT_FEEDS

    logger = logging.getLogger(__name__)
    created = 0

    for feed_def in DEFAULT_FEEDS:
        result = await db.execute(select(Feed).where(Feed.name == feed_def["name"]))
        if result.scalar_one_or_none() is not None:
            continue

        auth_encrypted = None
        enabled = feed_def.get("enabled", True)

        api_key_env = feed_def.get("requires_api_key_env")
        if api_key_env:
            api_key = os.environ.get(api_key_env, "")
            if api_key:
                auth_config = {
                    **feed_def["auth_config_template"],
                    "api_key": api_key,
                }
                auth_encrypted = encrypt_config(json.dumps(auth_config))
            else:
                enabled = False
                logger.warning(
                    "Feed '%s' created disabled — set %s to enable",
                    feed_def["name"],
                    api_key_env,
                )

        feed = Feed(
            name=feed_def["name"],
            description=feed_def.get("description"),
            feed_type=feed_def["feed_type"],
            url=feed_def.get("url"),
            config=feed_def.get("config"),
            schedule_cron=feed_def.get("schedule_cron"),
            enabled=enabled,
            auth_config_encrypted=auth_encrypted,
            default_ttl_days=feed_def.get("default_ttl_days"),
        )
        db.add(feed)
        created += 1

    if created:
        await db.flush()

    return created
