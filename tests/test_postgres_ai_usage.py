"""Opt-in PostgreSQL checks for AI usage admission under real concurrency (#17).

Run with CTI_TEST_POSTGRES_URL=postgresql+psycopg_async://... pytest
 tests/test_postgres_ai_usage.py. Uses a random temporary schema with every
 migration applied; the database user needs CREATE SCHEMA permission.

Each simulated request uses its own session (its own connection), so the
policy-row ``SELECT … FOR UPDATE`` is what keeps admissions from overrunning
the concurrency limit or the budget.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cti.core.security import encrypt_config
from cti.models.ai import AiProvider, AiProviderConfig
from cti.models.ai_usage import AiAction, AiModelPricing, AiUsagePolicy, AiUsageRecord
from cti.models.audit import ActorType
from cti.schemas.ai import AiErrorCategory
from cti.services.ai import gateway
from cti.services.ai.base import INFERENCE_PROMPT, AdapterUsage
from cti.services.audit import Actor

MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
N = 12
ACTOR = Actor(ActorType.USER, None, "pg-concurrency")


def apply_migrations(connection: Any) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        for path in sorted(MIGRATIONS.glob("*.py")):
            spec = importlib.util.spec_from_file_location(f"cti_pg_ai_usage_{path.stem}", path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()


@pytest.fixture
async def pg_factory():  # type: ignore[no-untyped-def]
    url = os.getenv("CTI_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set CTI_TEST_POSTGRES_URL to run PostgreSQL AI usage concurrency checks")
    if not url.startswith("postgresql+psycopg_async://"):
        pytest.fail("CTI_TEST_POSTGRES_URL must use the postgresql+psycopg_async driver")
    schema = f"cti_ai_usage_test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(url)
    schema_engine = create_async_engine(
        url,
        connect_args={"options": f"-c search_path={schema}"},
        pool_size=N + 2,
        max_overflow=N,
    )
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with schema_engine.begin() as connection:
            await connection.run_sync(apply_migrations)
        factory = async_sessionmaker(schema_engine, expire_on_commit=False)
        async with factory() as db:
            db.add(
                AiProviderConfig(
                    provider=AiProvider.OPENAI,
                    credentials_encrypted=encrypt_config({"api_key": "sk-test-pg-0000"}),
                )
            )
            db.add(
                AiModelPricing(
                    provider="openai",
                    model="gpt-test",
                    input_usd_per_mtok=Decimal("1000"),
                    output_usd_per_mtok=Decimal("1000"),
                )
            )
            await db.commit()
        yield factory
    finally:
        await schema_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


class HeldAdapter:
    """Keeps every admitted request in flight until released."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.calls = 0

    async def inference_test(self, *_: object, **__: object) -> AdapterUsage:
        self.calls += 1
        await self.release.wait()
        return AdapterUsage(input_tokens=1, output_tokens=1)


async def _set_policy(factory: Any, **values: Any) -> None:
    async with factory() as db:
        await db.execute(update(AiUsagePolicy).where(AiUsagePolicy.id == 1).values(**values))
        await db.commit()


async def _attempt(factory: Any, adapter: HeldAdapter) -> AiErrorCategory | None:
    try:
        await gateway.run_inference(
            factory,
            actor=ACTOR,
            action=AiAction.INFERENCE_TEST,
            provider=AiProvider.OPENAI,
            model="gpt-test",
            prompt=INFERENCE_PROMPT,
            approved=None,
            retry_of=None,
            adapter=adapter,  # type: ignore[arg-type]
        )
    except gateway.GatewayRejectionError as exc:
        return exc.error.category
    return None


async def _run_simultaneously(factory: Any, adapter: HeldAdapter) -> tuple[list[Any], int]:
    """Start N admissions at once; once all have admitted or failed, count reservations."""
    tasks = [asyncio.create_task(_attempt(factory, adapter)) for _ in range(N)]
    # Wait until every task has either been rejected or is held in the adapter.
    for _ in range(500):
        rejected = sum(1 for task in tasks if task.done())
        if rejected + adapter.calls == N:
            break
        await asyncio.sleep(0.01)
    async with factory() as db:
        in_flight = int(
            await db.scalar(select(func.count()).where(AiUsageRecord.status == "reserved")) or 0
        )
    adapter.release.set()
    return list(await asyncio.gather(*tasks)), in_flight


async def test_simultaneous_admissions_never_exceed_concurrency(pg_factory: Any) -> None:
    await _set_policy(pg_factory, max_concurrent_requests=3, max_requests_per_minute=600)
    adapter = HeldAdapter()

    results, in_flight = await _run_simultaneously(pg_factory, adapter)

    assert in_flight == 3
    assert adapter.calls == 3
    assert results.count(None) == 3
    assert results.count(AiErrorCategory.CONCURRENCY_LIMIT) == N - 3
    async with pg_factory() as db:
        statuses = (await db.scalars(select(AiUsageRecord.status))).all()
    assert sorted(statuses) == ["succeeded"] * 3  # rejections write no record


async def test_simultaneous_admissions_never_exceed_budget(pg_factory: Any) -> None:
    # Each reservation is (30 + 64 + 1024) * $1000 / 1e6 = $1.118.
    await _set_policy(
        pg_factory,
        max_concurrent_requests=50,
        max_requests_per_minute=600,
        monthly_budget_usd=Decimal("4.5"),
    )
    adapter = HeldAdapter()

    results, in_flight = await _run_simultaneously(pg_factory, adapter)

    assert in_flight == 4  # 4 * 1.118 = 4.472 <= 4.5 < 5 * 1.118
    assert results.count(None) == 4
    assert results.count(AiErrorCategory.BUDGET_EXCEEDED) == N - 4
    async with pg_factory() as db:
        start, end = gateway.month_bounds(*gateway.current_month())
        spent = await gateway.committed_spend(db, start, end)
    # Settled with known (tiny) costs, committed spend is far below the budget.
    assert spent <= Decimal("4.5")


# ── migration 011 down and up again, and the usage report, on PostgreSQL ──


def _migration_011() -> Any:
    path = MIGRATIONS / "011_add_ai_usage.py"
    spec = importlib.util.spec_from_file_location("cti_pg_migration_011_again", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_011_schema(connection: Any) -> None:
    from sqlalchemy import inspect

    inspector = inspect(connection)
    assert {"ai_usage_policy", "ai_model_pricing", "ai_usage_records"} <= set(
        inspector.get_table_names()
    )
    indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("ai_usage_records")}
    assert indexes == {
        "ix_ai_usage_records_started_at": ["started_at"],
        "ix_ai_usage_records_provider_model": ["provider", "model", "started_at"],
    }
    [fk] = inspector.get_foreign_keys("ai_usage_records")
    assert (fk["referred_table"], fk["constrained_columns"]) == ("users", ["actor_user_id"])
    assert fk["options"].get("ondelete") == "SET NULL"
    checks = {c["name"] for c in inspector.get_check_constraints("ai_usage_policy")}
    assert "ck_ai_usage_policy_singleton" in checks
    policy = connection.execute(text("SELECT * FROM ai_usage_policy")).mappings().all()
    assert [{k: v for k, v in row.items() if k != "updated_at"} for row in policy] == [
        {
            "id": 1,
            "monthly_budget_usd": None,
            "max_output_tokens": 1024,
            "max_concurrent_requests": 2,
            "max_requests_per_minute": 10,
            "unpriced_model_policy": "block",
        }
    ]
    # Constraints are live: a second policy row and a bad status are refused.
    for statement in (
        "INSERT INTO ai_usage_policy (id) VALUES (2)",
        "INSERT INTO ai_usage_records (id, action, provider, model, status, billable, "
        "started_at, usage_source, cost_source) VALUES (gen_random_uuid(), 'inference_test', "
        "'openai', 'm', 'done', 'unknown', now(), 'unknown', 'unknown')",
    ):
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text(statement))


def _down_and_up(connection: Any) -> None:
    from sqlalchemy import inspect

    migration = _migration_011()
    _assert_011_schema(connection)
    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
    tables = set(inspect(connection).get_table_names())
    assert not {"ai_usage_policy", "ai_model_pricing", "ai_usage_records"} & tables
    assert "users" in tables
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    _assert_011_schema(connection)

    # ON DELETE SET NULL survives the round trip.
    user_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO users (id, username, email, password_hash, role) "
            "VALUES (:id, 'pg-user', 'pg@example.test', 'x', 'admin')"
        ),
        {"id": user_id},
    )
    record_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO ai_usage_records (id, actor_user_id, actor_label, action, provider, "
            "model, status, billable, started_at, usage_source, cost_source) VALUES (:id, "
            ":user, 'pg-user', 'inference_test', 'openai', 'm', 'reserved', 'unknown', now(), "
            "'unknown', 'unknown')"
        ),
        {"id": record_id, "user": user_id},
    )
    connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    row = connection.execute(
        text("SELECT actor_user_id, actor_label FROM ai_usage_records WHERE id = :id"),
        {"id": record_id},
    ).one()
    assert tuple(row) == (None, "pg-user")


async def test_migration_011_down_and_up_again_on_postgresql(pg_factory: Any) -> None:
    async with pg_factory() as db:
        connection = await db.connection()
        await connection.run_sync(_down_and_up)
        await db.commit()


async def test_usage_report_buckets_utc_days_whatever_the_session_time_zone(
    pg_factory: Any,
) -> None:
    from datetime import UTC, datetime

    from cti.services.ai_settings_service import usage_report

    def record(started_at: datetime, **values: Any) -> AiUsageRecord:
        row: dict[str, Any] = {
            "action": "inference_test",
            "provider": "openai",
            "model": "gpt-test",
            "status": "succeeded",
            "billable": "yes",
            "started_at": started_at,
            "usage_source": "unknown",
            "cost_source": "unknown",
        }
        row.update(values)
        return AiUsageRecord(**row)

    async with pg_factory() as db:
        # 03:00 UTC on 2 November is still 1 November in Los Angeles.
        db.add(
            record(
                datetime(2026, 11, 2, 3, 0, tzinfo=UTC),
                input_tokens=10,
                output_tokens=2,
                cost_usd=Decimal("0.25"),
                reserved_usd=Decimal("1"),
            )
        )
        db.add(
            record(
                datetime(2026, 11, 2, 23, 0, tzinfo=UTC),
                status="failed",
                billable="no",
                reserved_usd=Decimal("3"),
            )
        )
        await db.commit()
        await db.execute(text("SET TIME ZONE 'America/Los_Angeles'"))

        report = await usage_report(db, 2026, 11)

    assert [(d.date.isoformat(), d.requests) for d in report.by_day] == [("2026-11-02", 2)]
    totals = report.totals
    assert (totals.requests, totals.succeeded, totals.failed) == (2, 1, 1)
    assert (totals.input_tokens, totals.output_tokens) == (10, 2)
    assert (totals.token_unknown_requests, totals.cost_unknown_requests) == (1, 1)
    assert (totals.estimated_cost_usd, totals.committed_usd) == ("0.250000", "0.250000")


async def test_usage_report_bounds_breakdown_and_sums_exactly_on_postgresql(
    pg_factory: Any,
) -> None:
    """The top-N breakdown, its exact remainder and exact numeric sums on PostgreSQL."""
    from datetime import UTC, datetime

    from cti.services.ai_settings_service import USAGE_BREAKDOWN_LIMIT, usage_report

    large = Decimal("99999999.999999")
    small = Decimal("0.000001")
    started = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    models = USAGE_BREAKDOWN_LIMIT + 5
    costs = [large] * 1000 + [small]
    async with pg_factory() as db:
        for index, cost in enumerate(costs):
            db.add(
                AiUsageRecord(
                    action="inference_test",
                    provider="openai",
                    # Model 0 gets the bulk; the rest one or two records each.
                    model=f"model-{max(0, index - len(costs) + models):03d}",
                    status="succeeded",
                    billable="yes",
                    started_at=started,
                    usage_source="unknown",
                    cost_usd=cost,
                    cost_source="estimated",
                )
            )
        await db.commit()

        report = await usage_report(db, 2026, 11)

    expected = f"{large * 1000 + small:.6f}"
    assert report.totals.requests == len(costs)
    assert (report.totals.estimated_cost_usd, report.totals.committed_usd) == (expected, expected)
    assert len(report.by_provider_model) == USAGE_BREAKDOWN_LIMIT
    assert report.by_provider_model[0].model == "model-000"
    assert report.by_provider_model_omitted_groups == models - USAGE_BREAKDOWN_LIMIT
    other = report.by_provider_model_other
    assert other is not None
    listed = [*report.by_provider_model, other]
    assert sum(row.requests for row in listed) == report.totals.requests
    assert f"{sum(Decimal(row.estimated_cost_usd) for row in listed):.6f}" == expected
    assert f"{sum(Decimal(row.committed_usd) for row in listed):.6f}" == expected
