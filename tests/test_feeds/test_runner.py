from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from cti.feeds import runner
from cti.feeds.base import FeedResult, RawObservable
from cti.models.feed import Feed, FeedRun, FeedRunStatus, FeedType
from cti.models.observable import Observable, ObservableType


async def test_successful_feed_run_invalidates_observable_caches_once(
    db_session,
    monkeypatch,
) -> None:
    feed = Feed(
        name="Runner success",
        feed_type=FeedType.FILE,
        url="https://example.test/feed.txt",
    )
    db_session.add(feed)
    await db_session.commit()
    connector = MagicMock()
    connector.ingest = AsyncMock(
        return_value=FeedResult(
            observables=[RawObservable(type=ObservableType.DOMAIN_NAME, value="runner.example")]
        )
    )
    monkeypatch.setattr(runner, "get_connector", lambda *_args, **_kwargs: connector)
    invalidate = AsyncMock()
    monkeypatch.setattr(runner, "invalidate_observable_caches", invalidate)

    await runner.run_feed(feed.id, db_session)

    invalidate.assert_awaited_once_with()
    run = await db_session.scalar(select(FeedRun).where(FeedRun.feed_id == feed.id))
    assert run is not None and run.status is FeedRunStatus.SUCCESS


async def test_failed_feed_run_invalidates_after_a_partial_batch_commit(
    db_session,
    monkeypatch,
) -> None:
    feed = Feed(
        name="Runner partial failure",
        feed_type=FeedType.FILE,
        url="https://example.test/feed.txt",
    )
    db_session.add(feed)
    await db_session.commit()
    connector = MagicMock()
    connector.ingest = AsyncMock(
        return_value=FeedResult(
            observables=[RawObservable(type=ObservableType.DOMAIN_NAME, value="partial.example")]
        )
    )
    monkeypatch.setattr(runner, "get_connector", lambda *_args, **_kwargs: connector)

    async def commit_then_fail(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        db_session.add(
            Observable(
                type=ObservableType.DOMAIN_NAME,
                value="partial.example",
                confidence_score=50,
            )
        )
        await db_session.commit()
        raise RuntimeError("later batch failed")

    monkeypatch.setattr(runner.observable_service, "bulk_upsert_from_feed", commit_then_fail)
    invalidate = AsyncMock()
    monkeypatch.setattr(runner, "invalidate_observable_caches", invalidate)

    await runner.run_feed(feed.id, db_session)

    invalidate.assert_awaited_once_with()
    assert await db_session.scalar(select(Observable).where(Observable.value == "partial.example"))
    run = await db_session.scalar(select(FeedRun).where(FeedRun.feed_id == feed.id))
    assert run is not None
    assert run.status is FeedRunStatus.FAILURE
    assert run.error_message == "later batch failed"
