"""Dual-mode confidence scoring and time-based decay."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import case, func, select, update

from cti.core.redis import invalidate_observable_caches
from cti.models.observable import Observable
from cti.models.observable_source import ObservableSource
from cti.models.report import report_observables

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from cti.feeds.base import RawObservable
    from cti.models.feed import Feed

logger = logging.getLogger(__name__)


async def recompute_effective_confidence(
    db: AsyncSession,
    observable_ids: Iterable[uuid.UUID],
) -> None:
    """Recompute effective confidence for observables in one set-based update."""
    ids = list(set(observable_ids))
    if not ids:
        return

    max_feed_confidence = (
        select(func.max(ObservableSource.source_confidence))
        .where(ObservableSource.observable_id == Observable.id)
        .correlate(Observable)
        .scalar_subquery()
    )
    max_report_confidence = (
        select(func.max(report_observables.c.analyst_confidence))
        .where(report_observables.c.observable_id == Observable.id)
        .correlate(Observable)
        .scalar_subquery()
    )
    analyst_and_feed_floor = func.greatest(
        max_feed_confidence,
        Observable.manual_confidence,
        max_report_confidence,
    )
    await db.execute(
        update(Observable)
        .where(Observable.id.in_(ids))
        .values(
            confidence_score=case(
                (
                    Observable.confidence_override.is_not(None),
                    Observable.confidence_override,
                ),
                else_=func.coalesce(
                    analyst_and_feed_floor,
                    Observable.confidence_score,
                ),
            )
        )
    )


def compute_source_confidence(raw: RawObservable, feed: Feed) -> int:
    """Compute confidence for a specific feed's observation.

    Mode 1 -- Feed provides a native score:
        Clamp the raw score to ``[0, 100]``.
    Mode 2 -- Feed has no score:
        Use ``feed.default_confidence``.
    """
    if raw.native_confidence is not None:
        return max(0, min(100, raw.native_confidence))
    return feed.default_confidence


@dataclass
class DecaySettings:
    """Tunables for confidence decay, typically derived from app settings."""

    enabled: bool = True
    decay_days: int = 30
    decay_rate: int = 5  # points per week after stale cutoff
    decay_floor: int = 10


async def apply_confidence_decay(db: AsyncSession, settings: DecaySettings) -> int:
    """Apply time-based confidence decay to all stale observable sources.

    Sources whose ``last_seen_by_feed`` is older than ``decay_days`` have
    their ``source_confidence`` reduced by ``decay_rate`` per week beyond
    the cutoff, down to a minimum of ``decay_floor``.

    After adjusting source confidences the effective
    ``Observable.confidence_score`` (= MAX across all sources) is
    recomputed for every affected observable.

    Returns:
        The number of observables whose effective confidence changed.
    """
    if not settings.enabled:
        return 0

    # Use a timezone-naive UTC "now" so arithmetic works with the naive
    # datetimes read back from ``last_seen_by_feed``; the column is
    # timezone-naive in both SQLite and Postgres.
    now = datetime.now(UTC).replace(tzinfo=None)
    stale_cutoff = now - timedelta(days=settings.decay_days)

    # Find stale sources whose NATIVE score still has room to decay.
    result = await db.execute(
        select(ObservableSource).where(
            ObservableSource.last_seen_by_feed < stale_cutoff,
            ObservableSource.native_confidence > settings.decay_floor,
        )
    )

    affected_observable_ids: set[uuid.UUID] = set()

    for source in result.scalars():
        days_stale = (now - source.last_seen_by_feed).days
        weeks_stale = max(1, (days_stale - settings.decay_days) // 7)
        new_conf = max(
            settings.decay_floor,
            source.native_confidence - (weeks_stale * settings.decay_rate),
        )
        if new_conf != source.source_confidence:
            source.source_confidence = new_conf
            affected_observable_ids.add(source.observable_id)

    await recompute_effective_confidence(db, affected_observable_ids)

    if affected_observable_ids:
        await db.commit()
        await invalidate_observable_caches()
        logger.info(
            "Confidence decay applied to %d observables",
            len(affected_observable_ids),
        )

    return len(affected_observable_ids)
