"""APScheduler integration with Redis job store for feed scheduling."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.services import feed_service
from cti.services.confidence import DecaySettings, apply_confidence_decay

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None

OBSERVABLE_RETENTION_JOB_ID = "system:observable_retention"
AUDIT_RETENTION_JOB_ID = "system:audit_retention"


def init_scheduler(redis_url: str) -> AsyncIOScheduler:
    """Initialize APScheduler with a Redis-backed job store."""
    global scheduler  # noqa: PLW0603
    settings = get_settings()
    password = settings.REDIS_PASSWORD.get_secret_value() or None
    jobstores = {
        "default": RedisJobStore(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=password,
        ),
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    """Return the active scheduler instance.

    Raises:
        RuntimeError: If :func:`init_scheduler` has not been called.
    """
    if scheduler is None:
        raise RuntimeError("Scheduler not initialized")
    return scheduler


async def sync_feed_jobs(db: AsyncSession) -> None:
    """Synchronise APScheduler jobs with the feeds table.

    * Adds or reschedules a job for every enabled feed with a cron schedule.
    * Removes stale jobs for feeds that have been disabled or deleted.
    """
    sched = get_scheduler()
    feeds = await feed_service.list_enabled_feeds_with_schedule(db)

    existing_jobs: set[str] = {
        job.id for job in sched.get_jobs() if job.id.startswith("feed:")
    }

    for feed in feeds:
        job_id = f"feed:{feed.id}"
        try:
            trigger = CronTrigger.from_crontab(feed.schedule_cron)
        except ValueError:
            logger.warning(
                "Invalid cron for feed %s: %s", feed.name, feed.schedule_cron
            )
            continue

        if job_id in existing_jobs:
            sched.reschedule_job(job_id, trigger=trigger)
            existing_jobs.discard(job_id)
        else:
            sched.add_job(
                _run_feed_job,
                trigger=trigger,
                id=job_id,
                args=[feed.id],
                replace_existing=True,
                misfire_grace_time=300,
            )

    # Remove jobs for feeds that are no longer enabled or have been deleted.
    for stale_job_id in existing_jobs:
        sched.remove_job(stale_job_id)

    logger.info("Synced %d feed jobs", len(feeds))


async def add_decay_job() -> None:
    """Register the periodic confidence-decay job."""
    sched = get_scheduler()
    settings = get_settings()
    sched.add_job(
        _run_decay_job,
        IntervalTrigger(hours=settings.CONFIDENCE_DECAY_INTERVAL_HOURS),
        id="system:confidence_decay",
        replace_existing=True,
    )


async def add_token_cleanup_job() -> None:
    """Register the periodic refresh-token cleanup job (runs daily)."""
    sched = get_scheduler()
    sched.add_job(
        _run_token_cleanup_job,
        IntervalTrigger(hours=24),
        id="system:token_cleanup",
        replace_existing=True,
    )


async def add_audit_retention_job(sched: AsyncIOScheduler | None = None) -> None:
    """Register daily audit-history retention (03:30 UTC; cannot be disabled).

    Pass the scheduler being started; defaults to :func:`get_scheduler`.
    """
    (sched or get_scheduler()).add_job(
        _run_audit_retention_job,
        CronTrigger(hour=3, minute=30, timezone="UTC"),
        id=AUDIT_RETENTION_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )


async def add_retention_job() -> None:
    """Register daily retention enforcement (zero retention days disables deletion).

    Each run writes one aggregated ``retention.observables_cleanup`` event.
    """
    get_scheduler().add_job(
        _run_retention_job,
        CronTrigger(hour=3, minute=0, timezone="UTC"),
        id=OBSERVABLE_RETENTION_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )


async def _run_retention_job() -> None:
    """APScheduler callback: enforce retention, then write one aggregated event."""
    from cti.core.database import async_session_factory
    from cti.services import audit
    from cti.services.retention import enforce_retention

    retention_days = get_settings().OBSERVABLE_RETENTION_DAYS
    summary: dict[str, object]
    async with async_session_factory() as db:
        try:
            deleted = await enforce_retention(db, retention_days)
        except Exception as exc:
            logger.error("Observable retention job failed", exc_info=True)
            outcome = audit.AuditOutcome.FAILED
            summary = {"retention_days": retention_days, "error_code": type(exc).__name__}
        else:
            outcome = audit.AuditOutcome.SUCCEEDED
            summary = {"deleted": deleted, "retention_days": retention_days}
    await audit.record_independent(
        actor=audit.system_actor(OBSERVABLE_RETENTION_JOB_ID, "Observable retention"),
        action="retention.observables_cleanup",
        resource_type="retention",
        outcome=outcome,
        summary=summary,
        strict=False,
    )


async def _run_audit_retention_job() -> None:
    """APScheduler callback: purge expired audit events, then record one event.

    Never one event per removed row. The cutoff is fixed before purging so the
    aggregated event written afterwards is never itself eligible.
    """
    from cti.core import database
    from cti.services import audit

    retention_days = get_settings().AUDIT_RETENTION_DAYS
    cutoff = audit.retention_cutoff(retention_days)
    summary: dict[str, object] = {"cutoff": cutoff.isoformat()}
    outcome = audit.AuditOutcome.SUCCEEDED
    try:
        async with database.async_session_factory() as db:
            summary["deleted"] = await audit.purge_expired_events(
                db, retention_days, now=cutoff + timedelta(days=retention_days)
            )
    except Exception as exc:
        outcome = audit.AuditOutcome.FAILED
        cause = exc.__cause__ if isinstance(exc, audit.AuditRetentionError) else exc
        summary["deleted"] = exc.deleted if isinstance(exc, audit.AuditRetentionError) else 0
        summary["error_code"] = type(cause or exc).__name__
        logger.error("Audit retention job failed (%s)", summary["error_code"])
    await audit.record_independent(
        actor=audit.system_actor(AUDIT_RETENTION_JOB_ID, "Audit retention"),
        action="audit.retention_cleanup",
        resource_type="audit",
        outcome=outcome,
        summary=summary,
        strict=False,
    )


async def _run_feed_job(feed_id: uuid.UUID) -> None:
    """APScheduler callback: execute a scheduled feed ingestion run."""
    # Late imports to avoid circular dependencies at module load time.
    from cti.core.database import async_session_factory
    from cti.feeds.runner import run_feed

    async with async_session_factory() as db:
        try:
            await run_feed(feed_id, db)
        except Exception:
            logger.error(
                "Scheduled feed run failed: %s", feed_id, exc_info=True
            )


async def _run_decay_job() -> None:
    """APScheduler callback: run confidence decay across all sources."""
    from cti.core.database import async_session_factory

    settings = get_settings()
    decay_settings = DecaySettings(
        enabled=settings.CONFIDENCE_DECAY_ENABLED,
        decay_days=settings.CONFIDENCE_DECAY_DAYS,
        decay_rate=settings.CONFIDENCE_DECAY_RATE,
        decay_floor=settings.CONFIDENCE_DECAY_FLOOR,
    )

    async with async_session_factory() as db:
        try:
            count = await apply_confidence_decay(db, decay_settings)
            if count:
                logger.info("Decay job affected %d observables", count)
        except Exception:
            logger.error("Confidence decay job failed", exc_info=True)


async def _run_token_cleanup_job() -> None:
    """APScheduler callback: delete expired refresh tokens."""
    from cti.core.database import async_session_factory
    from cti.services.auth_service import cleanup_expired_tokens

    async with async_session_factory() as db:
        try:
            count = await cleanup_expired_tokens(db)
            if count:
                logger.info("Token cleanup removed %d expired tokens", count)
        except Exception:
            logger.error("Token cleanup job failed", exc_info=True)
