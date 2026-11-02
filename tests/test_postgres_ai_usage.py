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
