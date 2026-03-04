"""Feed run orchestrator -- executes a single feed ingestion cycle."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.redis import invalidate_blocklist_cache
from cti.core.security import decrypt_config
from cti.feeds import get_connector
from sqlalchemy import select

from cti.models.feed import FeedRun, FeedRunStatus
from cti.services import feed_service
from cti.services import observable_service

logger = logging.getLogger(__name__)


async def run_feed(
    feed_id: uuid.UUID, db: AsyncSession, run_id: uuid.UUID | None = None
) -> None:
    """Execute a single feed ingestion run.

    1. Loads the feed and creates (or reuses) a ``FeedRun`` record.
    2. Instantiates the appropriate connector, fetches and normalises data.
    3. Bulk-upserts the resulting observables.
    4. Marks the run as success/failure and invalidates the blocklist cache.
    """
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise ValueError(f"Feed not found: {feed_id}")
    if not feed.url:
        raise ValueError(f"Feed has no URL: {feed.name}")

    if run_id:
        result = await db.execute(select(FeedRun).where(FeedRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"FeedRun not found: {run_id}")
    else:
        run = await feed_service.create_feed_run(db, feed.id)
        await db.commit()

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

        ingested, new = await observable_service.bulk_upsert_from_feed(
            db, feed, result.observables
        )

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

        # Invalidate blocklist cache after successful ingestion.
        try:
            await invalidate_blocklist_cache()
        except Exception:
            logger.warning("Failed to invalidate blocklist cache", exc_info=True)

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
        logger.error("Feed %s failed: %s", feed.name, e, exc_info=True)
