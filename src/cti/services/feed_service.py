"""Feed CRUD operations and default feed seeding."""

from __future__ import annotations

import logging
import os
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


def _preconfigured_auth_template(feed: Feed) -> dict | None:
    """Return the auth_config_template for a preconfigured feed, or None."""
    if not feed.is_preconfigured:
        return None
    for d in DEFAULT_FEEDS:
        if d["name"] == feed.name:
            return d.get("auth_config_template")
    return None


async def update_feed(db: AsyncSession, feed: Feed, data: dict) -> Feed:
    """Update a feed.

    For preconfigured feeds only ``enabled``, ``schedule_cron``,
    ``default_confidence``, and ``auth_config`` may be modified.

    If ``data`` contains ``auth_config``:
    - When ``auth_type`` is present in the payload, the supplied dict fully
      replaces the stored auth config.
    - Otherwise the payload is treated as a *partial* update: ``api_key_value``
      is merged into the existing decrypted config (if any) or the feed's
      preconfigured template.  For bearer-auth feeds ``token`` is also set.
    - Raises ``ValueError`` if no base config structure can be determined.
    """
    auth_config = data.pop("auth_config", None)

    if feed.is_preconfigured:
        allowed = {"enabled", "schedule_cron", "default_confidence", "auth_config"}
        data = {k: v for k, v in data.items() if k in allowed and v is not None}

    for key, value in data.items():
        if value is not None:
            setattr(feed, key, value)

    if auth_config:
        if "auth_type" in auth_config:
            # Full replace — caller supplied a complete auth config
            merged = auth_config
        else:
            # Partial update: route the secret into an existing base
            if feed.auth_config_encrypted:
                base = decrypt_config(feed.auth_config_encrypted)
            else:
                tmpl = _preconfigured_auth_template(feed)
                if tmpl is None:
                    raise ValueError(
                        "No auth config to merge into: supply auth_type or set one first"
                    )
                base = dict(tmpl)
            merged = dict(base)
            merged["api_key_value"] = auth_config["api_key_value"]
            if base.get("auth_type") == "bearer":
                merged["token"] = auth_config["api_key_value"]
        feed.auth_config_encrypted = encrypt_config(merged)

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

        # Wire up API key from environment if available
        env_var = feed_def.get("requires_api_key")
        template = feed_def.get("auth_config_template")
        if env_var and template:
            api_key_value = os.environ.get(env_var, "")
            if api_key_value:
                auth_config = dict(template)
                auth_config["api_key_value"] = api_key_value
                if template.get("auth_type") == "bearer":
                    auth_config["token"] = api_key_value
                feed.auth_config_encrypted = encrypt_config(auth_config)
                logger.info(
                    "Feed %s: API key populated from %s", feed_def["name"], env_var
                )

        db.add(feed)
        count += 1

    if count:
        await db.flush()
        logger.info("Seeded %d default feeds", count)

    return count


async def update_preconfigured_feeds(db: AsyncSession) -> int:
    """Sync URL, config, feed_type, and auth hints from defaults for existing preconfigured feeds.

    Does NOT overwrite user-set fields: enabled, schedule_cron,
    default_confidence, auth_config_encrypted.

    Returns the number of feeds updated.
    """
    defaults_by_name = {d["name"]: d for d in DEFAULT_FEEDS}

    result = await db.execute(
        select(Feed).where(Feed.is_preconfigured.is_(True))
    )
    feeds = list(result.scalars().all())

    updated = 0
    for feed in feeds:
        feed_def = defaults_by_name.get(feed.name)
        if not feed_def:
            continue

        changed = False

        # Sync URL
        new_url = feed_def.get("url")
        if new_url and feed.url != new_url:
            feed.url = new_url
            changed = True

        # Sync config
        new_config = feed_def.get("config")
        if new_config and feed.config != new_config:
            feed.config = new_config
            changed = True

        # Sync feed_type
        new_feed_type = feed_def.get("feed_type")
        if new_feed_type and feed.feed_type != new_feed_type:
            feed.feed_type = new_feed_type
            changed = True

        # Wire up API key from env if feed doesn't already have auth
        env_var = feed_def.get("requires_api_key")
        template = feed_def.get("auth_config_template")
        if env_var and template and not feed.auth_config_encrypted:
            api_key_value = os.environ.get(env_var, "")
            if api_key_value:
                auth_config = dict(template)
                auth_config["api_key_value"] = api_key_value
                if template.get("auth_type") == "bearer":
                    auth_config["token"] = api_key_value
                feed.auth_config_encrypted = encrypt_config(auth_config)
                changed = True
                logger.info(
                    "Feed %s: API key populated from %s", feed.name, env_var
                )

        if changed:
            updated += 1

    # Remove deprecated preconfigured feeds no longer in DEFAULT_FEEDS
    default_names = set(defaults_by_name.keys())
    for feed in feeds:
        if feed.name not in default_names:
            if not feed.enabled:
                await db.delete(feed)
                logger.info("Removed deprecated preconfigured feed: %s", feed.name)
            else:
                feed.is_preconfigured = False
                logger.info("Deprecated feed %s is enabled; converting to custom feed", feed.name)

    if updated:
        await db.flush()
        logger.info("Updated %d preconfigured feeds from defaults", updated)

    return updated


async def list_enabled_feeds_with_schedule(db: AsyncSession) -> list[Feed]:
    """Get all enabled feeds that have a cron schedule configured."""
    result = await db.execute(
        select(Feed).where(
            Feed.enabled.is_(True),
            Feed.schedule_cron.isnot(None),
        )
    )
    return list(result.scalars().all())
