from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from cti.feeds.base import RawObservable
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services import confidence, feed_service, observable_service
from cti.services.confidence import (
    DecaySettings,
    apply_confidence_decay,
    recompute_effective_confidence,
)


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


async def test_recompute_effective_confidence_chunks_ids(db_session, monkeypatch) -> None:
    feed = Feed(name="Chunk feed", feed_type=FeedType.FILE)
    observables = [
        Observable(
            type=ObservableType.DOMAIN_NAME,
            value=f"chunk-{index}.example",
            confidence_score=1,
        )
        for index in range(5)
    ]
    db_session.add_all([feed, *observables])
    await db_session.flush()
    db_session.add_all(
        [
            ObservableSource(
                observable_id=observable.id,
                feed_id=feed.id,
                source_confidence=50 + index,
                native_confidence=50 + index,
            )
            for index, observable in enumerate(observables)
        ]
    )
    await db_session.flush()

    monkeypatch.setattr(confidence, "_RECOMPUTE_BATCH_SIZE", 2)
    await recompute_effective_confidence(db_session, [observable.id for observable in observables])
    await db_session.flush()

    for index, observable in enumerate(observables):
        refreshed = await db_session.get(Observable, observable.id, populate_existing=True)
        assert refreshed is not None
        assert refreshed.confidence_score == 50 + index


async def test_delete_feed_recomputes_remaining_source_and_respects_manual_floor(
    db_session,
) -> None:
    high_feed = Feed(name="High feed", feed_type=FeedType.FILE)
    low_feed = Feed(name="Low feed", feed_type=FeedType.FILE)
    db_session.add_all([high_feed, low_feed])
    await db_session.commit()
    raws = [
        RawObservable(type="domain-name", value="feed-floor.example", native_confidence=90),
        RawObservable(type="domain-name", value="feed-only-drop.example", native_confidence=90),
    ]
    await observable_service.bulk_upsert_from_feed(db_session, high_feed, raws)
    await observable_service.bulk_upsert_from_feed(
        db_session,
        low_feed,
        [RawObservable(type=raw.type, value=raw.value, native_confidence=40) for raw in raws],
    )
    floored, _ = await observable_service.create_observable(
        db_session,
        ObservableType.DOMAIN_NAME,
        "feed-floor.example",
        70,
    )
    await db_session.commit()

    assert await feed_service.delete_feed(db_session, high_feed) is True
    await db_session.commit()

    floored = await db_session.get(Observable, floored.id, populate_existing=True)
    feed_only = await db_session.scalar(
        Observable.__table__.select()
        .with_only_columns(Observable.id)
        .where(Observable.value == "feed-only-drop.example")
    )
    assert floored is not None and floored.confidence_score == 70
    remaining = await db_session.get(Observable, feed_only, populate_existing=True)
    assert remaining is not None and remaining.confidence_score == 40


async def test_delete_only_feed_keeps_score_until_manual_input_replaces_it(db_session) -> None:
    feed = Feed(name="Only feed", feed_type=FeedType.FILE)
    db_session.add(feed)
    await db_session.commit()
    await observable_service.bulk_upsert_from_feed(
        db_session,
        feed,
        [RawObservable(type="domain-name", value="stale-score.example", native_confidence=90)],
    )
    observable_id = await db_session.scalar(
        Observable.__table__.select()
        .with_only_columns(Observable.id)
        .where(Observable.value == "stale-score.example")
    )

    assert await feed_service.delete_feed(db_session, feed) is True
    await db_session.commit()
    kept = await db_session.get(Observable, observable_id, populate_existing=True)
    assert kept is not None and kept.confidence_score == 90

    recreated, _ = await observable_service.create_observable(
        db_session,
        ObservableType.DOMAIN_NAME,
        "stale-score.example",
        60,
    )
    await db_session.commit()
    assert recreated.manual_confidence == 60
    assert recreated.confidence_score == 60


async def test_deprecated_preconfigured_feed_removal_recomputes_confidence(db_session) -> None:
    retired = Feed(
        name="Retired confidence feed",
        feed_type=FeedType.FILE,
        is_preconfigured=True,
        enabled=False,
    )
    remaining = Feed(name="Remaining confidence feed", feed_type=FeedType.FILE)
    observable = Observable(
        type=ObservableType.DOMAIN_NAME,
        value="deprecated-feed.example",
        confidence_score=90,
    )
    db_session.add_all([retired, remaining, observable])
    await db_session.flush()
    db_session.add_all(
        [
            ObservableSource(
                observable_id=observable.id,
                feed_id=retired.id,
                source_confidence=90,
                native_confidence=90,
            ),
            ObservableSource(
                observable_id=observable.id,
                feed_id=remaining.id,
                source_confidence=40,
                native_confidence=40,
            ),
        ]
    )
    await db_session.commit()

    await feed_service.update_preconfigured_feeds(db_session)
    await db_session.commit()

    refreshed = await db_session.get(Observable, observable.id, populate_existing=True)
    assert refreshed is not None and refreshed.confidence_score == 40


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
