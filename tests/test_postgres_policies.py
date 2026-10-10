"""Opt-in PostgreSQL checks for migration, row-lock and FK behavior.

Run with CTI_TEST_POSTGRES_URL=postgresql+psycopg_async://... uv run pytest
 tests/test_postgres_policies.py. Uses a random temporary schema, never public
 tables; the supplied database user needs CREATE SCHEMA permission.
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.export_profile import ExportFormat, ExportProfile
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services.retention import enforce_retention

MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def apply_migrations(connection):
    """Exercise the production migration functions on the isolated schema."""
    with Operations.context(MigrationContext.configure(connection)):
        for path in sorted(MIGRATIONS.glob("*.py")):
            spec = importlib.util.spec_from_file_location(f"cti_test_migration_{path.stem}", path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()


@pytest.fixture
async def pg_sessions():
    url = os.getenv("CTI_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set CTI_TEST_POSTGRES_URL to run isolated PostgreSQL policy checks")
    if not url.startswith("postgresql+psycopg_async://"):
        pytest.fail("CTI_TEST_POSTGRES_URL must use the postgresql+psycopg_async driver")
    schema = f"cti_policy_test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(url)
    schema_engine = create_async_engine(url, connect_args={"options": f"-c search_path={schema}"})
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with schema_engine.begin() as connection:
            await connection.run_sync(apply_migrations)
        yield async_sessionmaker(schema_engine, expire_on_commit=False)
    finally:
        await schema_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


async def test_postgres_feed_responses_do_not_lazy_load(pg_sessions):
    from cti.api.v1.feeds import _feed_to_response
    from cti.services.feed_service import create_feed, update_feed

    async with pg_sessions() as db:
        feed = await create_feed(
            db, {"name": "New custom feed", "feed_type": FeedType.FILE, "enabled": False}
        )
        await db.commit()
        response = _feed_to_response(feed)
        assert response.name == "New custom feed"
        assert response.latest_run is None
        assert response.observable_count == 0

        await update_feed(db, feed, {"description": "Updated feed"})
        await db.commit()
        response = _feed_to_response(feed)
        assert response.description == "Updated feed"
        assert response.updated_at is not None
        assert response.latest_run is None


async def test_postgres_retention_skips_locked_rows_and_keeps_refreshed_rows(pg_sessions):
    now = datetime.now(UTC).replace(tzinfo=None)
    async with pg_sessions() as setup:
        obs = Observable(
            type=ObservableType.IP_ADDR, value="10.0.0.1", last_seen=now - timedelta(days=200)
        )
        setup.add(obs)
        await setup.commit()
        obs_id = obs.id
    async with pg_sessions() as ingestion, pg_sessions() as cleanup:
        row = await ingestion.scalar(
            select(Observable).where(Observable.id == obs_id).with_for_update()
        )
        assert row is not None
        # Must terminate without waiting for the simulated active feed's lock.
        import asyncio

        assert await asyncio.wait_for(enforce_retention(cleanup, 180, now=now), timeout=5) == 0
        row.last_seen = now
        await ingestion.commit()
        assert await enforce_retention(cleanup, 180, now=now) == 0
        assert await cleanup.get(Observable, obs_id) is not None


async def test_postgres_retention_deletes_sources_but_retains_policies(pg_sessions):
    now = datetime.now(UTC).replace(tzinfo=None)
    async with pg_sessions() as db:
        feed = Feed(name="PG policy check", feed_type=FeedType.FILE)
        obs = Observable(
            type=ObservableType.IP_ADDR, value="10.0.0.2", last_seen=now - timedelta(days=200)
        )
        entry = AllowlistEntry(
            kind=AllowlistKind.EXACT,
            value="10.0.0.2",
            observable_type=ObservableType.IP_ADDR,
            reason="Known good",
        )
        db.add_all([feed, obs, entry])
        await db.flush()
        profile = ExportProfile(name="PG export", format=ExportFormat.TEXT, feed_id=feed.id)
        source = ObservableSource(observable_id=obs.id, feed_id=feed.id)
        db.add_all([profile, source])
        await db.commit()
        # Retention owns the session's transactions; its final rollback expires
        # ORM instances even with expire_on_commit=False. Keep primitive IDs.
        entry_id, profile_id = entry.id, profile.id
        assert await enforce_retention(db, 180, now=now) == 1
        assert await db.scalar(select(Observable.id)) is None
        assert await db.scalar(select(ObservableSource.id)) is None
        assert await db.scalar(select(AllowlistEntry.id)) == entry_id
        assert await db.scalar(select(ExportProfile.id)) == profile_id


async def test_postgres_streamed_export_filters_before_limit_and_loads_sources(
    pg_sessions,
    monkeypatch,
):
    from cti.services import observable_service

    monkeypatch.setattr(observable_service, "_EXPORT_PAGE_SIZE", 2)
    monkeypatch.setattr(observable_service, "_BATCH_SIZE", 2)
    now = datetime.now(UTC).replace(tzinfo=None)
    async with pg_sessions() as db:
        feed = Feed(name="Streaming source", feed_type=FeedType.FILE)
        blocked = Observable(
            type=ObservableType.IP_ADDR,
            value="10.0.0.1",
            last_seen=now,
            confidence_score=90,
        )
        permitted = [
            Observable(
                type=ObservableType.IP_ADDR,
                value=f"192.0.2.{i}",
                last_seen=now - timedelta(minutes=i + 1),
                confidence_score=90,
            )
            for i in range(5)
        ]
        db.add_all([feed, blocked, *permitted])
        await db.flush()
        db.add_all(
            [
                ObservableSource(observable_id=row.id, feed_id=feed.id)
                for row in [blocked, *permitted]
            ]
        )
        db.add(
            AllowlistEntry(
                kind=AllowlistKind.CIDR,
                value="10.0.0.0/8",
                observable_type=ObservableType.IP_ADDR,
                reason="Streaming suppression test",
            )
        )
        await db.commit()
        values = await observable_service.get_export_json(db, feed_id=feed.id, limit=3)
        assert [row.value for row in values] == ["192.0.2.0", "192.0.2.1", "192.0.2.2"]
        assert all(row.sources[0].feed.name == "Streaming source" for row in values)
        complete = await observable_service.get_export_json(db, feed_id=feed.id, limit=None)
        assert len(complete) == 5


async def test_postgres_profile_foreign_key_restricts_raw_feed_deletion(pg_sessions):
    async with pg_sessions() as db:
        feed = Feed(name="Referenced PG feed", feed_type=FeedType.FILE)
        db.add(feed)
        await db.flush()
        feed_id = feed.id
        profile = ExportProfile(name="Protected profile", format=ExportFormat.TEXT, feed_id=feed_id)
        db.add(profile)
        await db.commit()
        with pytest.raises(IntegrityError):
            await db.execute(delete(Feed).where(Feed.id == feed_id))
            await db.commit()
        await db.rollback()
        assert await db.get(Feed, feed_id) is not None
        stored = await db.scalar(select(ExportProfile))
        assert stored is not None and stored.feed_id == feed_id
