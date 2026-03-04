"""Dual-mode confidence scoring and time-based decay."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cti.feeds.base import RawObservable
from cti.models.feed import Feed
from cti.models.observable import Observable
from cti.models.observable_source import ObservableSource

logger = logging.getLogger(__name__)


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


async def apply_confidence_decay(
    db: AsyncSession, settings: DecaySettings
) -> int:
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

    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(days=settings.decay_days)

    # Find stale sources that are still above the floor.
    result = await db.execute(
        select(ObservableSource).where(
            ObservableSource.last_seen_by_feed < stale_cutoff,
            ObservableSource.source_confidence > settings.decay_floor,
        )
    )

    affected_observable_ids: set[uuid.UUID] = set()

    for source in result.scalars():
        days_stale = (now - source.last_seen_by_feed).days
        weeks_stale = max(1, (days_stale - settings.decay_days) // 7 + 1)
        new_conf = max(
            settings.decay_floor,
            source.source_confidence - (weeks_stale * settings.decay_rate),
        )
        if new_conf != source.source_confidence:
            source.source_confidence = new_conf
            affected_observable_ids.add(source.observable_id)

    # Recompute effective confidence for every affected observable.
    for obs_id in affected_observable_ids:
        max_result = await db.execute(
            select(func.max(ObservableSource.source_confidence)).where(
                ObservableSource.observable_id == obs_id
            )
        )
        new_effective = max_result.scalar_one() or settings.decay_floor
        await db.execute(
            update(Observable)
            .where(Observable.id == obs_id)
            .values(confidence_score=new_effective)
        )

    if affected_observable_ids:
        await db.commit()
        logger.info(
            "Confidence decay applied to %d observables",
            len(affected_observable_ids),
        )

    return len(affected_observable_ids)
