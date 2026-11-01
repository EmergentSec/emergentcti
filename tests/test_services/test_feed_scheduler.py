"""Scheduler behaviour when feed schedules are cleared or updated."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cti.models.feed import Feed, FeedType
from cti.services import scheduler


@pytest.mark.asyncio
async def test_sync_feed_jobs_removes_stale_job_when_schedule_cleared(
    db_session, monkeypatch
) -> None:
    feed = Feed(
        name="CronFeed",
        feed_type=FeedType.API,
        enabled=True,
        schedule_cron="0 * * * *",
    )
    db_session.add(feed)
    await db_session.commit()

    mock_sched = MagicMock()
    stale = MagicMock()
    stale.id = f"feed:{feed.id}"
    mock_sched.get_jobs.return_value = [stale]
    monkeypatch.setattr(scheduler, "scheduler", mock_sched)

    feed.schedule_cron = None
    await db_session.flush()

    await scheduler.sync_feed_jobs(db_session)

    mock_sched.remove_job.assert_called_once_with(f"feed:{feed.id}")


@pytest.mark.asyncio
async def test_sync_feed_jobs_does_not_add_job_for_manual_feed(
    db_session, monkeypatch
) -> None:
    feed = Feed(
        name="ManualFeed",
        feed_type=FeedType.API,
        enabled=True,
        schedule_cron=None,
    )
    db_session.add(feed)
    await db_session.commit()

    mock_sched = MagicMock()
    mock_sched.get_jobs.return_value = []
    monkeypatch.setattr(scheduler, "scheduler", mock_sched)

    await scheduler.sync_feed_jobs(db_session)

    mock_sched.add_job.assert_not_called()
    mock_sched.remove_job.assert_not_called()
