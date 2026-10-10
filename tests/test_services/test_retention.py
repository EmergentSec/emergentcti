"""Retention semantics, bounded transactions, cache invalidation and job wiring."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from cti.core.config import Settings
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services import retention, scheduler

NOW = datetime(2026, 10, 10, 12)


def indicator(value, days=None, *, created_days=200):
    return Observable(
        type=ObservableType.IP_ADDR,
        value=value,
        last_seen=NOW - timedelta(days=days) if days is not None else None,
        created_at=NOW - timedelta(days=created_days),
    )


async def count(db, model):
    return await db.scalar(select(func.count()).select_from(model))


async def test_deletes_old_and_unknown_stale_but_keeps_boundary_and_recent(db_session, monkeypatch):
    invalidate = AsyncMock()
    cache_delete = AsyncMock()
    monkeypatch.setattr(retention, "invalidate_blocklist_cache", invalidate)
    monkeypatch.setattr(retention, "cache_delete", cache_delete)
    rows = [
        indicator("10.0.0.1", 181),
        indicator("10.0.0.2", 180),  # Strictly older, not equal.
        indicator("10.0.0.3", 10),
        indicator("10.0.0.4", created_days=181),
        indicator("10.0.0.5", created_days=10),
    ]
    feed = Feed(name="Retention test", feed_type=FeedType.FILE)
    db_session.add_all([feed, *rows])
    await db_session.flush()
    db_session.add_all([ObservableSource(observable_id=row.id, feed_id=feed.id) for row in rows])
    await db_session.commit()

    # Batch size of one exercises multiple commits and eager/source deletion.
    assert await retention.enforce_retention(db_session, 180, now=NOW, batch_size=1) == 2
    remaining = (await db_session.scalars(select(Observable.value))).all()
    assert set(remaining) == {"10.0.0.2", "10.0.0.3", "10.0.0.5"}
    assert await count(db_session, ObservableSource) == 3
    assert await count(db_session, Feed) == 1
    assert invalidate.await_count == 2
    assert cache_delete.await_count == 2
    cache_delete.assert_awaited_with("stats:dashboard")
    assert await retention.enforce_retention(db_session, 180, now=NOW) == 0
    assert invalidate.await_count == 2


async def test_retention_does_not_delete_allowlist_or_profile_configuration(db_session):
    from cti.models.allowlist import AllowlistEntry, AllowlistKind
    from cti.models.export_profile import ExportFormat, ExportProfile

    db_session.add_all(
        [
            indicator("10.0.0.9", 181),
            AllowlistEntry(
                kind=AllowlistKind.EXACT,
                observable_type=ObservableType.IP_ADDR,
                value="10.0.0.9",
                reason="Known good; policy must survive indicator retention",
            ),
            ExportProfile(name="Retained policy", format=ExportFormat.TEXT),
        ]
    )
    await db_session.commit()
    assert await retention.enforce_retention(db_session, 180, now=NOW) == 1
    assert await count(db_session, AllowlistEntry) == 1
    assert await count(db_session, ExportProfile) == 1
    assert await count(db_session, Observable) == 0


async def test_zero_disables_retention_without_db_or_cache_access():
    db = AsyncMock()
    assert await retention.enforce_retention(db, 0) == 0
    db.execute.assert_not_awaited()
    db.scalars.assert_not_awaited()
    db.commit.assert_not_awaited()


async def test_invalid_parameters_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        await retention.enforce_retention(AsyncMock(), -1)
    with pytest.raises(ValueError, match="positive"):
        await retention.enforce_retention(AsyncMock(), 180, batch_size=0)
    with pytest.raises(ValidationError):
        Settings(OBSERVABLE_RETENTION_DAYS=-1, _env_file=None)
    assert Settings(OBSERVABLE_RETENTION_DAYS=0, _env_file=None).OBSERVABLE_RETENTION_DAYS == 0


async def test_aware_now_uses_utc_and_manual_rows_are_deleted(db_session):
    db_session.add(indicator("10.1.1.1", 181))
    await db_session.commit()
    assert await retention.enforce_retention(db_session, 180, now=NOW.replace(tzinfo=UTC)) == 1
    assert await count(db_session, Observable) == 0


async def test_failure_rolls_back_batch_and_does_not_invalidate(db_session, monkeypatch):
    row = indicator("10.1.1.2", 181)
    feed = Feed(name="Rollback source", feed_type=FeedType.FILE)
    db_session.add_all([row, feed])
    await db_session.flush()
    db_session.add(ObservableSource(observable_id=row.id, feed_id=feed.id))
    await db_session.commit()
    execute = db_session.execute
    invalidate = AsyncMock()
    monkeypatch.setattr(retention, "invalidate_blocklist_cache", invalidate)

    async def fail_observable_delete(stmt, *args, **kwargs):
        if getattr(stmt, "is_delete", False) and stmt.table.name == "observables":
            raise RuntimeError("simulated deletion failure")
        return await execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", fail_observable_delete)
    with pytest.raises(RuntimeError, match="simulated"):
        await retention.enforce_retention(db_session, 180, now=NOW)
    assert await count(db_session, Observable) == 1
    assert await count(db_session, ObservableSource) == 1
    invalidate.assert_not_awaited()


async def test_later_batch_failure_preserves_prior_commit_and_invalidation(db_session, monkeypatch):
    db_session.add_all([indicator("10.2.0.1", 181), indicator("10.2.0.2", 182)])
    await db_session.commit()
    execute = db_session.execute
    deletions = 0
    invalidate = AsyncMock()
    cache_delete = AsyncMock()
    monkeypatch.setattr(retention, "invalidate_blocklist_cache", invalidate)
    monkeypatch.setattr(retention, "cache_delete", cache_delete)

    async def fail_second_delete(stmt, *args, **kwargs):
        nonlocal deletions
        if getattr(stmt, "is_delete", False) and stmt.table.name == "observables":
            deletions += 1
            if deletions == 2:
                raise RuntimeError("second batch failed")
        return await execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", fail_second_delete)
    with pytest.raises(RuntimeError, match="second batch"):
        await retention.enforce_retention(db_session, 180, now=NOW, batch_size=1)
    assert await count(db_session, Observable) == 1
    invalidate.assert_awaited_once()
    cache_delete.assert_awaited_once_with("stats:dashboard")


async def test_scheduler_registers_daily_serialized_retention_job(monkeypatch):
    sched = MagicMock()
    monkeypatch.setattr(scheduler, "scheduler", sched)
    await scheduler.add_retention_job()
    args, kwargs = sched.add_job.call_args
    assert args[0] is scheduler._run_retention_job
    # Fixed UTC wall-clock schedule does not reset to 24h out on every restart.
    before = datetime(2026, 10, 10, 2, 59, tzinfo=UTC)
    assert args[1].get_next_fire_time(None, before) == datetime(2026, 10, 10, 3, tzinfo=UTC)
    assert args[1].get_next_fire_time(None, before + timedelta(seconds=30)) == datetime(
        2026,
        10,
        10,
        3,
        tzinfo=UTC,
    )
    assert kwargs["id"] == "system:observable_retention"
    assert kwargs["replace_existing"] is True
    assert kwargs["max_instances"] == 1
    assert kwargs["coalesce"] is True


async def test_job_invokes_retention_with_config_and_logs_failure(monkeypatch, caplog):
    from cti.core import database

    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=db)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    enforce = AsyncMock(side_effect=RuntimeError("failed"))
    monkeypatch.setattr(database, "async_session_factory", factory)
    monkeypatch.setattr(retention, "enforce_retention", enforce)
    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: Settings(
            OBSERVABLE_RETENTION_DAYS=17,
            _env_file=None,
        ),
    )
    await scheduler._run_retention_job()
    enforce.assert_awaited_once_with(db, 17)
    assert "Observable retention job failed" in caplog.text


async def test_lifespan_registers_retention_before_scheduler_starts(monkeypatch):
    from cti import main

    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=db)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(main, "async_session_factory", factory)
    for name in (
        "init_redis",
        "close_redis",
        "seed_initial_admin_user",
        "sync_feed_jobs",
        "add_decay_job",
        "add_token_cleanup_job",
    ):
        monkeypatch.setattr(main, name, AsyncMock())
    monkeypatch.setattr(main, "seed_initial_api_key", AsyncMock(return_value=None))
    monkeypatch.setattr(main.feed_service, "seed_default_feeds", AsyncMock(return_value=0))
    monkeypatch.setattr(main.feed_service, "update_preconfigured_feeds", AsyncMock())
    sched = MagicMock()
    monkeypatch.setattr(main, "init_scheduler", lambda _: sched)
    registered = AsyncMock()
    monkeypatch.setattr(main, "add_retention_job", registered)
    async with main.lifespan(MagicMock()):
        registered.assert_awaited_once()
        sched.start.assert_called_once()
    sched.shutdown.assert_called_once_with(wait=False)
