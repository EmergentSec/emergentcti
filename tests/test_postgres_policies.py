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
from sqlalchemy import delete, func, inspect, select, text, update
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


async def test_postgres_report_import_upserts_and_attribution_constraints(pg_sessions):
    """Migration 007 + import on PostgreSQL: ON CONFLICT paths, CHECK and SET NULL."""
    from cti.models.report import Report, report_observables
    from cti.models.user import User, UserRole
    from cti.schemas.report import ImportItem
    from cti.services import report_import_service, report_service

    async with pg_sessions() as db:
        user = User(username="pg-importer", password_hash="unused", role=UserRole.admin)
        # An analyst-created observable: since #28 its confidence is recorded
        # as manual_confidence (the floor that report imports cannot lower).
        existing = Observable(
            type=ObservableType.IP_ADDR,
            value="185.220.101.42",
            confidence_score=90,
            manual_confidence=90,
        )
        report = Report(
            title="PG import",
            origin="internal",
            content="C2 evil-pg[.]example and 185.220.101.42",
        )
        db.add_all([user, existing, report])
        await db.commit()
        # Capture ids now: rollback() below expires every instance, and reading
        # an expired attribute would trigger a sync lazy load under asyncio.
        user_id, existing_id, report_id = user.id, existing.id, report.id
        report = await report_service.get_report(db, report_id)
        items = [
            ImportItem(type="domain-name", value="evil-pg.example"),
            ImportItem(type="ip-addr", value="185.220.101.42"),
        ]

        result = await report_import_service.import_candidates(
            db, report, confidence=55, items=items, imported_by_id=user_id
        )
        await db.commit()
        assert (result.created, result.attributed_existing, result.already_attributed) == (1, 1, 0)

        again = await report_import_service.import_candidates(
            db, report, confidence=5, items=items, imported_by_id=user_id
        )
        await db.commit()
        assert (again.created, again.attributed_existing, again.already_attributed) == (0, 0, 2)
        assert await db.scalar(select(func.count()).select_from(Observable)) == 2
        assert (
            await db.get(Observable, existing_id, populate_existing=True)
        ).confidence_score == 90

        with pytest.raises(IntegrityError):
            await db.execute(
                report_observables.update()
                .where(report_observables.c.report_id == report_id)
                .values(analyst_confidence=101)
            )
        await db.rollback()

        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()
        imported_by = (
            await db.scalars(
                select(report_observables.c.imported_by_id).where(
                    report_observables.c.report_id == report_id
                )
            )
        ).all()
        assert imported_by == [None, None]


async def test_postgres_confidence_recompute_and_constraints(pg_sessions):
    """Migration 008 CHECKs and the shared floor/override UPDATE on PostgreSQL."""
    from cti.models.report import Report, report_observables
    from cti.models.user import User, UserRole
    from cti.services.confidence import recompute_effective_confidence

    async with pg_sessions() as db:
        feed = Feed(name="PG confidence", feed_type=FeedType.FILE)
        report = Report(title="PG confidence report", origin="internal")
        setter = User(username="pg-confidence-setter", password_hash="unused", role=UserRole.admin)
        observable = Observable(
            type=ObservableType.DOMAIN_NAME,
            value="confidence-pg.example",
            confidence_score=10,
            manual_confidence=40,
        )
        db.add_all([feed, report, setter, observable])
        await db.flush()
        db.add(
            ObservableSource(
                observable_id=observable.id,
                feed_id=feed.id,
                source_confidence=60,
                native_confidence=60,
            )
        )
        await db.execute(
            report_observables.insert().values(
                report_id=report.id,
                observable_id=observable.id,
                analyst_confidence=80,
            )
        )
        await recompute_effective_confidence(db, [observable.id])
        await db.commit()
        observable_id = observable.id
        stored = await db.get(Observable, observable_id, populate_existing=True)
        assert stored is not None and stored.confidence_score == 80

        stored.confidence_override = 5
        stored.override_set_at = datetime.now(UTC)
        stored.override_set_by_id = setter.id
        await recompute_effective_confidence(db, [observable_id])
        await db.commit()
        setter_id = setter.id
        stored = await db.get(Observable, observable_id, populate_existing=True)
        assert stored is not None and stored.confidence_score == 5

        await db.execute(delete(User).where(User.id == setter_id))
        await db.commit()
        stored = await db.get(Observable, observable_id, populate_existing=True)
        assert stored is not None and stored.override_set_by_id is None

        invalid_updates = [
            {"manual_confidence": 101},
            {"confidence_override": -1},
            {
                "confidence_override": None,
                "override_set_at": datetime.now(UTC),
            },
        ]
        for values in invalid_updates:
            with pytest.raises(IntegrityError):
                await db.execute(
                    update(Observable).where(Observable.id == observable_id).values(**values)
                )
                await db.commit()
            await db.rollback()


async def test_postgres_migration_009_tlp_and_tags(pg_sessions):
    """Migration 009 on PostgreSQL: CHECKs, RESTRICT, effective SQL, export gate, down/up."""
    from cti.models.report import Report, report_observables
    from cti.models.tag import Tag, export_profile_tags, observable_tags
    from cti.services import observable_service
    from cti.services.tlp import effective_tlp_map

    async with pg_sessions() as db:
        # Rollout: pre-existing profiles default to internal.
        profile = ExportProfile(name="PG 009", format=ExportFormat.TEXT, confidence_min=0)
        red_feed = Feed(name="PG red", feed_type=FeedType.FILE, tlp="red")
        unspecified_feed = Feed(name="PG unspecified", feed_type=FeedType.FILE)
        green_report = Report(title="PG green", origin="internal", tlp="green")
        amber_report = Report(title="PG amber", origin="internal", tlp="amber")
        red_obs = Observable(type=ObservableType.IP_ADDR, value="192.0.2.90")
        poisoned = Observable(type=ObservableType.IP_ADDR, value="192.0.2.91")
        amber_obs = Observable(type=ObservableType.IP_ADDR, value="192.0.2.92")
        manual = Observable(type=ObservableType.IP_ADDR, value="192.0.2.93", manual_tlp="clear")
        db.add_all(
            [
                profile,
                red_feed,
                unspecified_feed,
                green_report,
                amber_report,
                red_obs,
                poisoned,
                amber_obs,
                manual,
            ]
        )
        await db.flush()
        db.add_all(
            [
                ObservableSource(observable_id=red_obs.id, feed_id=red_feed.id),
                ObservableSource(observable_id=poisoned.id, feed_id=unspecified_feed.id),
                ObservableSource(observable_id=amber_obs.id, feed_id=unspecified_feed.id),
            ]
        )
        await db.execute(
            report_observables.insert().values(
                [
                    {"report_id": green_report.id, "observable_id": red_obs.id},
                    {"report_id": green_report.id, "observable_id": poisoned.id},
                    {"report_id": amber_report.id, "observable_id": amber_obs.id},
                ]
            )
        )
        await db.commit()
        assert (await db.get(ExportProfile, profile.id)).destination.value == "internal"

        markings = await effective_tlp_map(db, [red_obs.id, poisoned.id, amber_obs.id, manual.id])
        assert {k: (v.value if v else None) for k, v in markings.items()} == {
            red_obs.id: "red",
            poisoned.id: None,
            amber_obs.id: "amber",
            manual.id: "clear",
        }
        values, _allowlisted, by_tlp = await observable_service.get_export_values(
            db, order="value", line_safe=True
        )
        assert values == ["192.0.2.91", "192.0.2.92", "192.0.2.93"]
        assert by_tlp["red"] == 1
        public, _a, _t = await observable_service.get_export_values(db, destination="public")
        assert public == ["192.0.2.93"]

        for statement in (
            update(Feed).where(Feed.id == red_feed.id).values(tlp="TLP:RED"),
            update(Report).where(Report.id == green_report.id).values(tlp="white"),
            update(Observable).where(Observable.id == manual.id).values(tlp_override="red"),
            update(ExportProfile)
            .where(ExportProfile.id == profile.id)
            .values(destination="external_ai"),
        ):
            with pytest.raises(IntegrityError):
                await db.execute(statement)
                await db.commit()
            await db.rollback()

        tag = Tag(name="pg-tag")
        db.add(tag)
        await db.flush()
        await db.execute(observable_tags.insert().values(observable_id=red_obs.id, tag_id=tag.id))
        await db.execute(
            export_profile_tags.insert().values(export_profile_id=profile.id, tag_id=tag.id)
        )
        await db.commit()
        tag_id = tag.id
        with pytest.raises(IntegrityError):
            await db.execute(delete(Tag).where(Tag.id == tag_id))
            await db.commit()
        await db.rollback()
        # Deleting the observable cascades its tag assignments.
        await db.execute(delete(Observable).where(Observable.id == red_obs.id))
        await db.commit()
        remaining = await db.scalar(
            select(func.count())
            .select_from(observable_tags)
            .where(observable_tags.c.tag_id == tag_id)
        )
        assert remaining == 0

    # Downgrade 009 -> 008 and upgrade again on the same schema.
    path = MIGRATIONS / "009_add_tags_and_tlp.py"
    spec = importlib.util.spec_from_file_location("cti_test_migration_009_pg", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def run(connection, direction):
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, direction)()

    engine = pg_sessions.kw["bind"]
    async with engine.begin() as connection:
        await connection.run_sync(run, "downgrade")
        tables = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
        assert not {"tags", "observable_tags", "report_tags", "export_profile_tags"} & tables
        await connection.run_sync(run, "upgrade")
