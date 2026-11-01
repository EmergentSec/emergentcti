from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from cti.feeds.base import RawObservable
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services import observable_service
from cti.services.confidence import DecaySettings, apply_confidence_decay


async def test_manual_floor_survives_low_feed_and_higher_feed_raises(db_session) -> None:
    observable, _ = await observable_service.create_observable(
        db_session,
        ObservableType.IP_ADDR,
        "192.0.2.20",
        80,
    )
    await db_session.commit()
    feed = Feed(name="Floor feed", feed_type=FeedType.FILE, default_confidence=20)
    db_session.add(feed)
    await db_session.commit()

    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="ip-addr", value="192.0.2.20", native_confidence=20)],
    )
    observable = await db_session.get(Observable, observable.id, populate_existing=True)
    assert observable is not None
    assert observable.manual_confidence == 80
    assert observable.confidence_score == 80

    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="ip-addr", value="192.0.2.20", native_confidence=95)],
    )
    observable = await db_session.get(Observable, observable.id, populate_existing=True)
    assert observable is not None and observable.confidence_score == 95


async def test_feed_only_scoring_is_unchanged(db_session) -> None:
    feed = Feed(name="Feed only", feed_type=FeedType.FILE, default_confidence=37)
    db_session.add(feed)
    await db_session.commit()
    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="domain-name", value="feed-only.example")],
    )
    observable = await db_session.get(
        Observable,
        await db_session.scalar(
            Observable.__table__.select()
            .with_only_columns(Observable.id)
            .where(Observable.value == "feed-only.example")
        ),
    )
    assert observable is not None
    assert observable.manual_confidence is None
    assert observable.confidence_score == 37


async def test_feed_ingest_invalidates_observable_caches(
    db_session,
    monkeypatch,
) -> None:
    invalidate = AsyncMock()
    monkeypatch.setattr(observable_service, "invalidate_observable_caches", invalidate)
    feed = Feed(name="Cache feed", feed_type=FeedType.FILE)
    db_session.add(feed)
    await db_session.commit()

    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="domain-name", value="cache-feed.example")],
    )

    invalidate.assert_awaited_once()


async def test_override_pins_feed_and_manual_updates_then_clear_recomputes(db_session) -> None:
    observable, _ = await observable_service.create_observable(
        db_session,
        ObservableType.DOMAIN_NAME,
        "pinned.example",
        60,
    )
    await db_session.commit()
    await observable_service.set_confidence_override(
        db_session,
        observable.id,
        5,
        set_by_id=None,
    )
    await db_session.commit()

    feed = Feed(name="Pinned feed", feed_type=FeedType.FILE, default_confidence=90)
    db_session.add(feed)
    await db_session.commit()
    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="domain-name", value="pinned.example", native_confidence=1)],
    )
    observable = await db_session.get(Observable, observable.id, populate_existing=True)
    assert observable is not None and observable.confidence_score == 5

    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="domain-name", value="pinned.example", native_confidence=90)],
    )
    await observable_service.create_observable(
        db_session,
        ObservableType.DOMAIN_NAME,
        "pinned.example",
        95,
    )
    await db_session.commit()
    observable = await db_session.get(Observable, observable.id, populate_existing=True)
    assert observable is not None
    assert observable.manual_confidence == 95
    assert observable.confidence_score == 5

    cleared = await observable_service.clear_confidence_override(db_session, observable.id)
    await db_session.commit()
    assert cleared is not None
    assert cleared.confidence_override is None
    assert cleared.confidence_score == 95


async def test_decay_respects_manual_floor_and_pinned_override(db_session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    feed = Feed(name="Decay floor", feed_type=FeedType.FILE)
    floored = Observable(
        type=ObservableType.IP_ADDR,
        value="192.0.2.30",
        confidence_score=90,
        manual_confidence=80,
    )
    pinned = Observable(
        type=ObservableType.IP_ADDR,
        value="192.0.2.31",
        confidence_score=4,
        confidence_override=4,
        override_set_at=now,
    )
    db_session.add_all([feed, floored, pinned])
    await db_session.flush()
    stale = now - timedelta(days=400)
    db_session.add_all(
        [
            ObservableSource(
                observable_id=observable.id,
                feed_id=feed.id,
                source_confidence=90,
                native_confidence=90,
                first_seen_by_feed=stale,
                last_seen_by_feed=stale,
            )
            for observable in (floored, pinned)
        ]
    )
    await db_session.commit()

    await apply_confidence_decay(
        db_session,
        DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10),
    )
    floored = await db_session.get(Observable, floored.id, populate_existing=True)
    pinned = await db_session.get(Observable, pinned.id, populate_existing=True)
    assert floored is not None and floored.confidence_score == 80
    assert pinned is not None and pinned.confidence_score == 4


async def test_decay_invalidates_observable_caches(db_session, monkeypatch) -> None:
    from cti.services import confidence

    invalidate = AsyncMock()
    monkeypatch.setattr(confidence, "invalidate_observable_caches", invalidate)
    now = datetime.now(UTC).replace(tzinfo=None)
    feed = Feed(name="Decay cache", feed_type=FeedType.FILE)
    observable = Observable(
        type=ObservableType.IP_ADDR,
        value="192.0.2.32",
        confidence_score=90,
    )
    db_session.add_all([feed, observable])
    await db_session.flush()
    stale = now - timedelta(days=40)
    db_session.add(
        ObservableSource(
            observable_id=observable.id,
            feed_id=feed.id,
            source_confidence=90,
            native_confidence=90,
            first_seen_by_feed=stale,
            last_seen_by_feed=stale,
        )
    )
    await db_session.commit()

    await apply_confidence_decay(db_session, DecaySettings())

    invalidate.assert_awaited_once()
