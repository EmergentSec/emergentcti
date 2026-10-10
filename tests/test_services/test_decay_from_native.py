# tests/test_services/test_decay_from_native.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services.confidence import DecaySettings, apply_confidence_decay


async def _stale_source(db, days_stale: int, native: int = 90, value: str = "9.9.9.9"):
    feed = Feed(name=f"F-{value}", feed_type=FeedType.FILE, default_confidence=50)
    obs = Observable(type=ObservableType.IP_ADDR, value=value, confidence_score=native)
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


async def _source_confidence(db, src_id) -> int:
    src = (await db.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    return src.source_confidence


@pytest.mark.asyncio
async def test_decay_clamps_at_floor(db_session):
    src_id = await _stale_source(db_session, days_stale=400, native=90)  # ~52 weeks past cutoff
    settings = DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10)

    await apply_confidence_decay(db_session, settings)
    src = (await db_session.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    assert src.source_confidence == 10   # 90 - (52 * 5) would be negative; clamped to floor
    assert src.native_confidence == 90

    obs = (await db_session.execute(
        select(Observable).where(Observable.id == src.observable_id))).scalar_one()
    await db_session.refresh(obs)
    assert obs.confidence_score == 10


@pytest.mark.asyncio
async def test_decay_steps_one_rate_per_full_week(db_session):
    # weeks_stale = max(1, (days_stale - decay_days) // 7): the first bucket
    # decays one unit as soon as the source is stale.
    fresh = await _stale_source(db_session, days_stale=29, value="9.9.9.0")    # not stale
    just = await _stale_source(db_session, days_stale=31, value="9.9.9.1")     # 0 full weeks -> 1
    week1 = await _stale_source(db_session, days_stale=37, value="9.9.9.2")    # 1 week
    week2 = await _stale_source(db_session, days_stale=44, value="9.9.9.3")    # 2 weeks
    week3 = await _stale_source(db_session, days_stale=51, value="9.9.9.4")    # 3 weeks
    settings = DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10)

    await apply_confidence_decay(db_session, settings)

    assert await _source_confidence(db_session, fresh) == 90
    assert await _source_confidence(db_session, just) == 85    # 90 - (1 * 5)
    assert await _source_confidence(db_session, week1) == 85   # 90 - (1 * 5)
    assert await _source_confidence(db_session, week2) == 80   # 90 - (2 * 5)
    assert await _source_confidence(db_session, week3) == 75   # 90 - (3 * 5)


@pytest.mark.asyncio
async def test_decay_twice_gives_same_result(db_session):
    week3 = await _stale_source(db_session, days_stale=51, value="9.9.9.4")    # 3 weeks
    floored = await _stale_source(db_session, days_stale=400, value="9.9.9.5")
    settings = DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10)

    await apply_confidence_decay(db_session, settings)
    first = (await _source_confidence(db_session, week3),
             await _source_confidence(db_session, floored))
    assert first == (75, 10)

    # A second run recomputes from native_confidence, so nothing moves.
    changed = await apply_confidence_decay(db_session, settings)
    assert changed == 0
    assert (await _source_confidence(db_session, week3),
            await _source_confidence(db_session, floored)) == first
