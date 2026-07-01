# tests/test_services/test_decay_from_native.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services.confidence import DecaySettings, apply_confidence_decay


async def _stale_source(db, days_stale: int, native: int = 90):
    feed = Feed(name="F", feed_type=FeedType.FILE, default_confidence=50)
    obs = Observable(type=ObservableType.IP_ADDR, value="9.9.9.9", confidence_score=native)
    db.add_all([feed, obs])
    await db.commit()
    seen = datetime.now(UTC) - timedelta(days=days_stale)
    src = ObservableSource(
        observable_id=obs.id, feed_id=feed.id,
        source_confidence=native, native_confidence=native,
        first_seen_by_feed=seen, last_seen_by_feed=seen,
    )
    db.add(src)
    await db.commit()
    return src.id


@pytest.mark.asyncio
async def test_decay_is_idempotent_and_native_preserved(db_session):
    src_id = await _stale_source(db_session, days_stale=37, native=90)  # 1 week past 30d cutoff
    settings = DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10)

    await apply_confidence_decay(db_session, settings)
    src = (await db_session.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    first = src.source_confidence
    assert first == 85          # 90 - (1 week * 5)
    assert src.native_confidence == 90

    # Running again the same day must NOT decay further (the old bug double-subtracted).
    await apply_confidence_decay(db_session, settings)
    src = (await db_session.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    assert src.source_confidence == first
    assert src.native_confidence == 90
