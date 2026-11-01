"""Feed run orchestrator -- executes a single feed ingestion cycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from cti.core.redis import invalidate_observable_caches
from cti.core.security import decrypt_config
from cti.feeds import get_connector
from cti.feeds.defaults import DEFAULT_FEEDS
from cti.models.feed import FeedRun, FeedRunStatus
from cti.services import feed_service, observable_service

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

# Build a lookup of feeds that require API keys
_FEEDS_REQUIRING_KEY: dict[str, str] = {
    d["name"]: d["requires_api_key"] for d in DEFAULT_FEEDS if d.get("requires_api_key")
}

logger = logging.getLogger(__name__)


async def run_feed(feed_id: uuid.UUID, db: AsyncSession, run_id: uuid.UUID | None = None) -> None:
    """Execute a single feed ingestion run.

    1. Loads the feed and creates (or reuses) a ``FeedRun`` record.
    2. Instantiates the appropriate connector, fetches and normalises data.
    3. Bulk-upserts the resulting observables.
    4. Marks the run as success/failure and invalidates observable caches.
    """
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise ValueError(f"Feed not found: {feed_id}")
    if not feed.url:
        raise ValueError(f"Feed has no URL: {feed.name}")

    # Pre-run validation: fail fast if an API key is required but missing
    required_env_var = _FEEDS_REQUIRING_KEY.get(feed.name)
    if required_env_var and not feed.auth_config_encrypted:
        raise ValueError(
            f"Feed '{feed.name}' requires an API key ({required_env_var}) "
            f"but none is configured. Set {required_env_var} in your .env file "
            f"and restart, or configure auth via the API."
        )

    if run_id:
        result = await db.execute(select(FeedRun).where(FeedRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"FeedRun not found: {run_id}")
    else:
        run = await feed_service.create_feed_run(db, feed.id)
        await db.commit()

    ingest_attempted = False
    try:
        # Decrypt auth config if the feed has encrypted credentials.
        auth_config: dict | None = None
        if feed.auth_config_encrypted:
            auth_config = decrypt_config(feed.auth_config_encrypted)

        connector = get_connector(feed, auth_config=auth_config)
        result = await connector.ingest()

        if result.errors and not result.observables:
            # Complete failure -- no data to process.
            await feed_service.complete_feed_run(
                db,
                run,
                FeedRunStatus.FAILURE,
                error_message="; ".join(result.errors),
            )
            await db.commit()
            return

        ingest_attempted = True
        ingested, new = await observable_service.bulk_upsert_from_feed(db, feed, result.observables)

        feed.last_run_at = datetime.now(UTC)

        error_msg = "; ".join(result.errors) if result.errors else None
        await feed_service.complete_feed_run(
            db,
            run,
            FeedRunStatus.SUCCESS,
            observables_ingested=ingested,
            observables_new=new,
            error_message=error_msg,
        )
        await db.commit()

        # Bulk upsert commits per batch, but cache invalidation happens once per run.
        await invalidate_observable_caches()

        logger.info(
            "Feed %s completed: %d ingested, %d new",
            feed.name,
            ingested,
            new,
        )

    except Exception as e:
        await db.rollback()
        try:
            # Re-fetch the run after rollback so we can mark it as failed.
            if run_id:
                res = await db.execute(select(FeedRun).where(FeedRun.id == run_id))
                run = res.scalar_one_or_none()
            if run is None:
                run = await feed_service.create_feed_run(db, feed.id)
            await feed_service.complete_feed_run(
                db, run, FeedRunStatus.FAILURE, error_message=str(e)
            )
            await db.commit()
        except Exception:
            logger.error("Failed to record feed run failure", exc_info=True)
        if ingest_attempted:
            # A later batch may have failed after earlier batches committed.
            await invalidate_observable_caches()
        logger.error("Feed %s failed: %s", feed.name, e, exc_info=True)
