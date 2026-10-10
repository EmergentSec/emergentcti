"""Bounded, transactional deletion of observables outside the retention window."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from cti.core.redis import cache_delete, invalidate_blocklist_cache
from cti.models.observable import Observable
from cti.models.observable_source import ObservableSource

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def enforce_retention(
    db: AsyncSession,
    retention_days: int,
    *,
    now: datetime | None = None,
    batch_size: int = 1000,
) -> int:
    """Delete expired observables and sources, committing each bounded batch.

    Use a dedicated session: this function owns commits and rollback. Zero disables
    retention. Unknown last-seen values fall back to creation time. Allowlist rules
    are independent configuration, not exemptions from irreversible retention.

    PostgreSQL row locks prevent concurrent ingestion from refreshing a selected
    observable between the expiry check and deletion. Skip locked rows rather than
    interfering with active feed runs; they will be reconsidered on the next run.
    """
    if retention_days < 0:
        raise ValueError("retention_days must be nonnegative")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if retention_days == 0:
        return 0

    instant = now or datetime.now(UTC)
    # Both last_seen and created_at are timezone-naive database columns.
    if instant.tzinfo is not None:
        instant = instant.astimezone(UTC).replace(tzinfo=None)
    cutoff = instant - timedelta(days=retention_days)
    expired = func.coalesce(Observable.last_seen, Observable.created_at) < cutoff
    total = 0

    while True:
        try:
            ids = list(
                (
                    await db.scalars(
                        select(Observable.id)
                        .where(expired)
                        .order_by(Observable.id)
                        .limit(batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            if not ids:
                await db.rollback()  # Release the read transaction (and any locks).
                break
            # Explicit source deletion also works on SQLite with FK checks disabled.
            await db.execute(
                delete(ObservableSource).where(ObservableSource.observable_id.in_(ids))
            )
            await db.execute(delete(Observable).where(Observable.id.in_(ids)))
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Retention batch failed after %d committed deletions", total)
            raise

        total += len(ids)
        # Invalidate only after commit, including when a later batch fails.
        await invalidate_blocklist_cache()
        await cache_delete("stats:dashboard")

    if total:
        logger.info("Retention removed %d observables older than %d days", total, retention_days)
    return total
