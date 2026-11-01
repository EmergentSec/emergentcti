"""Feed CRUD operations and default feed seeding."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import encrypt_config
from cti.feeds.defaults import DEFAULT_FEEDS
from cti.models.export_profile import ExportProfile
from cti.models.feed import Feed, FeedRun, FeedRunStatus, FeedType
from cti.models.observable_source import ObservableSource
from cti.services.feed_auth import (
    REPAIR_MESSAGE,
    URL_TEMPLATE_URL_CHANGE_MESSAGE,
    AuthConfigValidationError,
    extract_partial_secret,
    try_decrypt_stored_auth,
    validate_auth_config,
)

logger = logging.getLogger(__name__)


class FeedInUseError(Exception):
    """The feed is referenced by saved export profiles and cannot be deleted."""

    def __init__(self, profile_names: list[str]) -> None:
        super().__init__(
            f"Feed is referenced by export profiles: {', '.join(profile_names) or 'unknown'}"
        )
        self.profile_names = profile_names


async def _referencing_profile_names(db: AsyncSession, feed_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(ExportProfile.name)
        .where(ExportProfile.feed_id == feed_id)
        .order_by(ExportProfile.name)
    )
    return [row[0] for row in result.all()]


def _normalize_clearable_string(value: str | None) -> str | None:
    """Map explicit null or blank strings to NULL for nullable text columns."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _apply_auth_config_update(
    feed: Feed,
    auth_config: dict,
    *,
    partial_only: bool,
) -> None:
    """Apply full or partial auth_config mutation after validation."""
    feed_url = feed.url

    if not partial_only:
        validated = validate_auth_config(auth_config, feed_url=feed_url)
        feed.auth_config_encrypted = encrypt_config(validated)
        return

    secret = extract_partial_secret(auth_config)
    if secret is None:
        return

    base: dict | None = None
    if feed.auth_config_encrypted is not None:
        decrypted = try_decrypt_stored_auth(feed.auth_config_encrypted)
        if decrypted is None:
            logger.warning(
                "Feed auth could not be decrypted during partial rotation",
                extra={"feed_id": str(feed.id)},
            )
        else:
            try:
                base = validate_auth_config(decrypted, feed_url=feed_url)
            except AuthConfigValidationError:
                base = None

    if base is None:
        template = _preconfigured_auth_template(feed)
        if template and isinstance(template.get("auth_type"), str):
            merged = dict(template)
            merged["api_key_value"] = secret
            if merged.get("auth_type") == "bearer":
                merged["token"] = secret
            try:
                validated = validate_auth_config(merged, feed_url=feed_url)
            except AuthConfigValidationError as exc:
                raise AuthConfigValidationError(REPAIR_MESSAGE) from exc
            feed.auth_config_encrypted = encrypt_config(validated)
            return
        raise AuthConfigValidationError(REPAIR_MESSAGE)

    merged = dict(base)
    merged["api_key_value"] = secret
    if merged.get("auth_type") == "bearer":
        merged["token"] = secret
    validated = validate_auth_config(merged, feed_url=feed_url)
    feed.auth_config_encrypted = encrypt_config(validated)


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
    # New feeds have no run history. Initialize it so response serialization
    # after commit never attempts relationship IO outside an async context.
    feed = Feed(**data, is_preconfigured=False, runs=[])
    if auth_config is not None:
        validated = validate_auth_config(auth_config, feed_url=feed.url)
        feed.auth_config_encrypted = encrypt_config(validated)
    db.add(feed)
    await db.flush()
    return feed


def _preconfigured_auth_template(feed: Feed) -> dict | None:
    """Return the auth_config_template for a preconfigured feed, or None."""
    if not feed.is_preconfigured:
        return None
    for d in DEFAULT_FEEDS:
        if d["name"] == feed.name:
            template = d.get("auth_config_template")
            # Return a copy — callers mutate this (e.g. set api_key_value) and
            # must never write a secret back into the shared DEFAULT_FEEDS global.
            return dict(template) if template else None
    return None


async def update_feed(db: AsyncSession, feed: Feed, data: dict) -> Feed:
    """Update a feed.

    For preconfigured feeds only ``enabled``, ``schedule_cron``,
    ``default_confidence``, ``description``, and ``auth_config`` may be
    modified (``name``/``url``/``feed_type``/``config`` are managed by the
    platform and ignored).

    If ``data`` contains ``auth_config``:
    - When ``auth_type`` is present in the payload, the supplied dict fully
      replaces the stored auth config.
    - Otherwise the payload is treated as a *partial* update: ``api_key_value``
      is merged into the existing decrypted config (if any) or the feed's
      preconfigured template.  For bearer-auth feeds ``token`` is also set.
    - Raises ``AuthConfigValidationError`` when auth_config is invalid.
    """
    auth_config_provided = "auth_config" in data
    auth_config = data.pop("auth_config", None) if auth_config_provided else None

    url_change_without_auth = (
        not feed.is_preconfigured
        and not auth_config_provided
        and "url" in data
        and data["url"] != feed.url
    )
    previous_url = feed.url

    if feed.is_preconfigured:
        allowed = {
            "enabled",
            "schedule_cron",
            "default_confidence",
            "auth_config",
            "description",
        }
        data = {k: v for k, v in data.items() if k in allowed}

    for key, value in data.items():
        if key in ("description", "schedule_cron"):
            setattr(
                feed,
                key,
                _normalize_clearable_string(value) if value is not None else None,
            )
        else:
            setattr(feed, key, value)

    if auth_config_provided and auth_config is not None:
        partial_only = "auth_type" not in auth_config
        _apply_auth_config_update(
            feed, auth_config, partial_only=partial_only
        )

    if url_change_without_auth and feed.auth_config_encrypted is not None:
        decrypted = try_decrypt_stored_auth(feed.auth_config_encrypted)
        if decrypted is not None:
            try:
                validate_auth_config(decrypted, feed_url=previous_url)
            except AuthConfigValidationError:
                pass
            else:
                try:
                    validate_auth_config(decrypted, feed_url=feed.url)
                except AuthConfigValidationError as exc:
                    raise AuthConfigValidationError(
                        URL_TEMPLATE_URL_CHANGE_MESSAGE
                    ) from exc

    await db.flush()
    # SQL-expression onupdate expires this field; load it while IO is awaited.
    await db.refresh(feed, attribute_names=["updated_at"])
    return feed


async def delete_feed(db: AsyncSession, feed: Feed) -> bool:
    """Delete a custom feed.

    Returns ``False`` (and does nothing) if the feed is preconfigured.

    Raises:
        FeedInUseError: a saved export profile filters on this feed. Deleting
            it would otherwise silently change what that profile exports.
    """
    if feed.is_preconfigured:
        return False
    profile_names = await _referencing_profile_names(db, feed.id)
    if profile_names:
        raise FeedInUseError(profile_names)
    feed_id = feed.id
    await db.delete(feed)
    try:
        await db.flush()
    except IntegrityError:
        # A profile started referencing the feed after the check above; the
        # database's ON DELETE RESTRICT refused the delete. Nothing was removed.
        await db.rollback()
        raise FeedInUseError(await _referencing_profile_names(db, feed_id)) from None
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
            if not feed.enabled and not await _referencing_profile_names(db, feed.id):
                await db.delete(feed)
                logger.info("Removed deprecated preconfigured feed: %s", feed.name)
            else:
                feed.is_preconfigured = False
                logger.info(
                    "Deprecated feed %s is enabled or referenced by an export profile; "
                    "converting to custom feed",
                    feed.name,
                )

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
