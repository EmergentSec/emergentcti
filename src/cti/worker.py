import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from celery import Celery
from croniter import croniter
from sqlalchemy import select

from cti.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

app = Celery("cti", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-scheduled-feeds": {
            "task": "cti.worker.check_scheduled_feeds",
            "schedule": 60.0,
        },
        "lifecycle-check": {
            "task": "cti.worker.lifecycle_check",
            "schedule": 3600.0,  # Every hour
        },
    },
)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_feed_task(self, feed_id: str) -> dict:  # type: ignore[no-untyped-def]
    from cti.core.database import get_sync_session
    from cti.feeds import get_connector
    from cti.models.feed import Feed, FeedRun, FeedRunStatus

    session = get_sync_session()
    try:
        feed = session.get(Feed, feed_id)
        if not feed:
            logger.error("Feed not found: %s", feed_id)
            return {"error": "Feed not found"}

        # Create run record
        run = FeedRun(feed_id=feed.id, status=FeedRunStatus.running)
        session.add(run)
        session.commit()

        try:
            connector = get_connector(feed)
            result = asyncio.run(connector.ingest())

            # Bulk create observables
            from sqlalchemy import func
            from sqlalchemy.dialects.postgresql import insert

            from cti.models.observable import Observable, observable_sources

            count = 0
            obs_ids: list[str] = []
            for item in result.observables:
                now = datetime.now(UTC)
                stmt = (
                    insert(Observable)
                    .values(
                        type=item.type,
                        value=item.value,
                        confidence_score=item.confidence_score,
                        first_seen=item.first_seen or now,
                        last_seen=item.last_seen or now,
                        tlp=item.tlp,
                        context=item.context,
                    )
                    .on_conflict_do_update(
                        constraint="uq_observable_type_value",
                        set_={
                            "last_seen": func.greatest(Observable.last_seen, item.last_seen or now),
                            "confidence_score": func.greatest(Observable.confidence_score, item.confidence_score),
                            "updated_at": now,
                        },
                    )
                    .returning(Observable.id)
                )
                obs_result = session.execute(stmt)
                obs_id = obs_result.scalar_one()
                obs_ids.append(str(obs_id))

                # Set expiration based on feed TTL
                if feed.default_ttl_days:
                    expires_at = datetime.now(UTC) + timedelta(days=feed.default_ttl_days)
                    session.execute(
                        sa.update(Observable)
                        .where(Observable.id == obs_id)
                        .values(expires_at=expires_at)
                    )

                session.execute(
                    insert(observable_sources)
                    .values(observable_id=obs_id, feed_id=feed.id)
                    .on_conflict_do_nothing()
                )
                count += 1

            # Update run as success
            run.status = FeedRunStatus.success
            run.observables_ingested = count
            run.completed_at = datetime.now(UTC)
            feed.last_run_at = datetime.now(UTC)
            session.commit()

            # Dispatch correlation evaluation (best effort)
            if obs_ids:
                try:
                    run_correlations_task.delay(obs_ids, feed_id=feed_id)
                except Exception:
                    logger.warning("Failed to dispatch correlation task", exc_info=True)

            # Auto-enrichment (best effort)
            if obs_ids:
                try:
                    auto_enrich_batch_task.delay(obs_ids)
                except Exception:
                    logger.warning("Failed to dispatch auto-enrichment task", exc_info=True)

            # Index to Elasticsearch (best effort)
            try:
                _index_to_es(session, obs_ids)
            except Exception:
                logger.warning("Failed to index to Elasticsearch", exc_info=True)

            logger.info("Feed %s ingested %d observables", feed.name, count)
            return {"status": "success", "observables_ingested": count}

        except Exception as e:
            run.status = FeedRunStatus.failure
            run.error_message = str(e)
            run.completed_at = datetime.now(UTC)
            session.commit()
            logger.error("Feed %s failed: %s", feed_id, e, exc_info=True)
            raise self.retry(exc=e) from e

    finally:
        session.close()


def _index_to_es(session, obs_ids: list[str]) -> None:  # type: ignore[no-untyped-def]
    import uuid

    from cti.core.elasticsearch import get_es_client
    from cti.models.observable import Observable
    from cti.services.search_service import bulk_index_observables, observable_model_to_es_doc

    obs_uuids = [uuid.UUID(i) for i in obs_ids]
    batch_size = 500
    all_docs: list[dict] = []

    for i in range(0, len(obs_uuids), batch_size):
        batch = obs_uuids[i : i + batch_size]
        result = session.execute(select(Observable).where(Observable.id.in_(batch)))
        for obs in result.scalars():
            all_docs.append(observable_model_to_es_doc(obs))

    async def _do_index() -> None:
        es = get_es_client()
        try:
            for i in range(0, len(all_docs), batch_size):
                await bulk_index_observables(es, all_docs[i : i + batch_size])
        finally:
            await es.close()

    asyncio.run(_do_index())
    logger.info("Indexed %d observables to Elasticsearch", len(all_docs))


@app.task
def check_scheduled_feeds() -> dict:
    from cti.core.database import get_sync_session
    from cti.models.feed import Feed

    logger.info("Checking scheduled feeds...")
    session = get_sync_session()
    try:
        result = session.execute(
            select(Feed).where(Feed.enabled.is_(True), Feed.schedule_cron.isnot(None))
        )
        feeds = result.scalars().all()
        triggered = 0

        now = datetime.now(UTC)
        for feed in feeds:
            try:
                cron = croniter(
                    feed.schedule_cron,
                    feed.last_run_at or datetime(2000, 1, 1, tzinfo=UTC),
                )
                next_run = cron.get_next(datetime)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=UTC)

                if next_run <= now:
                    feed.last_run_at = now  # Prevent re-trigger before task completes
                    run_feed_task.delay(str(feed.id))
                    triggered += 1
                    logger.info(
                        "Triggered scheduled feed: %s (next was %s)",
                        feed.name,
                        next_run,
                    )
            except Exception as e:
                logger.error(
                    "Failed to check schedule for feed %s: %s", feed.name, e
                )

        session.commit()  # Persist last_run_at updates
        logger.info("Scheduled feed check complete: %d triggered", triggered)
        return {"triggered": triggered}

    finally:
        session.close()


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def enrich_observable_task(
    self,  # type: ignore[no-untyped-def]
    observable_id: str,
    provider_name: str,
    user_id: str | None = None,
) -> dict:
    """Async enrichment task dispatched by the API."""
    from cti.core.database import async_session_factory
    from cti.services.enrichment_service import enrich_observable

    async def _run() -> dict:
        async with async_session_factory() as session:
            try:
                run = await enrich_observable(
                    session, observable_id, provider_name, user_id
                )
                await session.commit()
                return {
                    "status": run.status.value,
                    "provider": provider_name,
                    "observable_id": observable_id,
                    "summary": run.summary,
                }
            except Exception:
                await session.rollback()
                raise

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(
            "Enrichment failed: %s/%s: %s", provider_name, observable_id, e
        )
        raise self.retry(exc=e) from e


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_correlations_task(
    self,  # type: ignore[no-untyped-def]
    observable_ids: list[str],
    feed_id: str | None = None,
) -> dict:
    """Run correlation rules against a batch of observables."""
    import uuid

    from cti.core.database import async_session_factory
    from cti.services.correlation_service import evaluate_correlations_batch

    async def _run() -> dict:
        async with async_session_factory() as session:
            try:
                obs_uuids = [uuid.UUID(oid) for oid in observable_ids]
                feed_uuid = uuid.UUID(feed_id) if feed_id else None
                total = await evaluate_correlations_batch(
                    session, obs_uuids, feed_id=feed_uuid
                )
                await session.commit()
                return {
                    "status": "success",
                    "observables_evaluated": len(observable_ids),
                    "correlations_created": total,
                }
            except Exception:
                await session.rollback()
                raise

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error("Correlation task failed: %s", e, exc_info=True)
        raise self.retry(exc=e) from e


@app.task(bind=True, max_retries=1, default_retry_delay=60)
def auto_enrich_batch_task(self, observable_ids: list[str]) -> dict:  # type: ignore[no-untyped-def]
    """Dispatch auto-enrichment for a batch of observables."""
    import uuid

    from cti.core.database import async_session_factory
    from cti.enrichment.registry import get_enrichment_provider
    from cti.models.enrichment import EnrichmentConfig, EnrichmentRun
    from cti.models.observable import Observable

    async def _run() -> dict:
        async with async_session_factory() as session:
            try:
                dispatched = 0
                now = datetime.now(UTC)
                cutoff = now - timedelta(hours=24)

                for obs_id_str in observable_ids:
                    obs_uuid = uuid.UUID(obs_id_str)
                    obs = await session.get(Observable, obs_uuid)
                    if not obs:
                        continue

                    # Find auto-enrich configs with API keys
                    configs_result = await session.execute(
                        select(EnrichmentConfig).where(
                            EnrichmentConfig.enabled.is_(True),
                            EnrichmentConfig.auto_enrich.is_(True),
                            EnrichmentConfig.api_key_encrypted.isnot(None),
                        )
                    )
                    configs = configs_result.scalars().all()

                    for config in configs:
                        # Check if provider supports this observable type
                        provider = get_enrichment_provider(config.provider_name)
                        if not provider or not provider.supports_type(obs.type.value):
                            continue

                        # Check if enrichment was already run recently (within 24h)
                        recent_result = await session.execute(
                            select(EnrichmentRun).where(
                                EnrichmentRun.observable_id == obs_uuid,
                                EnrichmentRun.provider_name == config.provider_name,
                                EnrichmentRun.created_at > cutoff,
                            )
                        )
                        if recent_result.scalars().first():
                            continue

                        # Dispatch enrichment task
                        enrich_observable_task.delay(obs_id_str, config.provider_name)
                        dispatched += 1

                        # Rate-limit between dispatches
                        time.sleep(1)

                return {"dispatched": dispatched}
            except Exception:
                await session.rollback()
                raise

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error("Auto-enrichment batch failed: %s", e, exc_info=True)
        raise self.retry(exc=e) from e


@app.task
def lifecycle_check() -> dict:
    """Check for expired observables and apply confidence decay."""
    from cti.core.database import get_sync_session
    from cti.models.observable import Observable

    session = get_sync_session()
    try:
        now = datetime.now(UTC)

        # Step 1: Mark expired observables as inactive
        result = session.execute(
            sa.update(Observable)
            .where(
                Observable.expires_at.isnot(None),
                Observable.expires_at < now,
                Observable.is_active.is_(True),
            )
            .values(is_active=False)
        )
        expired = result.rowcount

        # Step 2: Apply confidence decay to stale observables not seen in 30+ days
        stale_cutoff = now - timedelta(days=30)
        stale_result = session.execute(
            select(Observable).where(
                Observable.last_seen < stale_cutoff,
                Observable.confidence_score > 10,
                Observable.is_active.is_(True),
            )
        )
        decayed = 0
        for obs in stale_result.scalars():
            weeks_stale = (now - obs.last_seen).days // 7
            new_score = max(10, obs.confidence_score - (weeks_stale * 5))
            if new_score != obs.confidence_score:
                obs.confidence_score = new_score
                decayed += 1

        session.commit()
        logger.info("Lifecycle check: %d expired, %d decayed", expired, decayed)
        return {"expired": expired, "decayed": decayed}

    finally:
        session.close()


@app.task
def reindex_elasticsearch() -> dict:
    from sqlalchemy import func

    from cti.core.database import get_sync_session
    from cti.core.elasticsearch import get_es_client
    from cti.models.observable import Observable
    from cti.services.search_service import (
        bulk_index_observables,
        ensure_index,
        observable_model_to_es_doc,
    )

    async def _index_batch(batch_docs: list, create_index: bool = False) -> None:  # type: ignore[type-arg]
        es = get_es_client()
        try:
            if create_index:
                await ensure_index(es)
            es_batch_size = 500
            for i in range(0, len(batch_docs), es_batch_size):
                await bulk_index_observables(es, batch_docs[i : i + es_batch_size])
        finally:
            await es.close()

    session = get_sync_session()
    try:
        total = session.execute(select(func.count(Observable.id))).scalar_one()
        logger.info("Reindex: %d total observables to index", total)

        db_batch_size = 1000
        indexed = 0
        is_first = True

        for offset in range(0, total, db_batch_size):
            result = session.execute(
                select(Observable).order_by(Observable.id).offset(offset).limit(db_batch_size)
            )
            docs = [observable_model_to_es_doc(obs) for obs in result.scalars()]

            asyncio.run(_index_batch(docs, create_index=is_first))
            is_first = False
            indexed += len(docs)
            session.expunge_all()
            logger.info("Reindex progress: %d / %d", indexed, total)

        logger.info("Reindex complete: %d indexed", indexed)
        return {"indexed": indexed}

    finally:
        session.close()


@app.task(bind=True, max_retries=1, default_retry_delay=30)
def generate_report_task(self, report_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Generate a report (HTML) as a background task."""
    import uuid

    from cti.core.database import async_session_factory
    from cti.services.report_generator import generate_report

    async def _run() -> dict:
        async with async_session_factory() as session:
            try:
                report_uuid = uuid.UUID(report_id)
                file_path = await generate_report(session, report_uuid)
                await session.commit()
                return {
                    "status": "ready",
                    "report_id": report_id,
                    "file_path": file_path,
                }
            except Exception:
                await session.rollback()
                raise

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error("Report generation failed for %s: %s", report_id, e, exc_info=True)
        raise self.retry(exc=e) from e
