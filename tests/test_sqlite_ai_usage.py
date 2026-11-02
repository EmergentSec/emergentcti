"""SQLite AI usage admission under real concurrency, one connection per request (#17).

The rest of the gateway suite routes every session through one shared
in-memory connection (see ``tests/conftest.py``), which serializes admissions
by construction. Here each simulated request gets its own session on its own
connection to a file-backed database, as in a production SQLite deployment, so
only the gateway's no-op policy ``UPDATE`` (SQLite's writer lock, taken before
any count or spend read) keeps simultaneous admissions under the caps.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from cti.core.security import encrypt_config
from cti.models import Base
from cti.models.ai import AiProvider, AiProviderConfig
from cti.models.ai_usage import AiModelPricing, AiUsagePolicy, AiUsageRecord
from cti.schemas.ai import AiErrorCategory
from cti.services.ai import gateway
from tests.test_postgres_ai_usage import HeldAdapter, N, _run_simultaneously

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@pytest.fixture
async def sqlite_factory(tmp_path: Path) -> AsyncGenerator[Any, None]:
    # NullPool: every session opens its own connection, never a shared one.
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'ai_usage.db'}",
        poolclass=NullPool,
        connect_args={"timeout": 30},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            db.add(gateway.default_policy())  # Migration 011's singleton row.
            db.add(
                AiProviderConfig(
                    provider=AiProvider.OPENAI,
                    credentials_encrypted=encrypt_config({"api_key": "sk-test-sqlite-0000"}),
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
        await engine.dispose()


async def _set_policy(factory: Any, **values: Any) -> None:
    async with factory() as db:
        await db.execute(update(AiUsagePolicy).where(AiUsagePolicy.id == 1).values(**values))
        await db.commit()


async def _statuses(factory: Any) -> list[str]:
    async with factory() as db:
        return sorted((await db.scalars(select(AiUsageRecord.status))).all())


async def test_simultaneous_sqlite_admissions_never_exceed_concurrency(
    sqlite_factory: Any,
) -> None:
    await _set_policy(sqlite_factory, max_concurrent_requests=3, max_requests_per_minute=600)
    adapter = HeldAdapter()

    results, in_flight = await _run_simultaneously(sqlite_factory, adapter)

    assert in_flight == 3
    assert adapter.calls == 3
    assert results.count(None) == 3
    assert results.count(AiErrorCategory.CONCURRENCY_LIMIT) == N - 3
    assert await _statuses(sqlite_factory) == ["succeeded"] * 3  # rejections write nothing


async def test_simultaneous_sqlite_admissions_never_exceed_rate(sqlite_factory: Any) -> None:
    await _set_policy(sqlite_factory, max_concurrent_requests=50, max_requests_per_minute=4)
    adapter = HeldAdapter()

    results, in_flight = await _run_simultaneously(sqlite_factory, adapter)

    assert in_flight == 4
    assert results.count(None) == 4
    assert results.count(AiErrorCategory.LOCAL_RATE_LIMITED) == N - 4
    assert await _statuses(sqlite_factory) == ["succeeded"] * 4


async def test_simultaneous_sqlite_admissions_never_exceed_budget(sqlite_factory: Any) -> None:
    # Each reservation is (30 + 64 + 1024) * $1000 / 1e6 = $1.118.
    await _set_policy(
        sqlite_factory,
        max_concurrent_requests=50,
        max_requests_per_minute=600,
        monthly_budget_usd=Decimal("4.5"),
    )
    adapter = HeldAdapter()

    results, in_flight = await _run_simultaneously(sqlite_factory, adapter)

    assert in_flight == 4  # 4 * 1.118 = 4.472 <= 4.5 < 5 * 1.118
    assert results.count(None) == 4
    assert results.count(AiErrorCategory.BUDGET_EXCEEDED) == N - 4
    async with sqlite_factory() as db:
        start, end = gateway.month_bounds(*gateway.current_month())
        assert await gateway.committed_spend(db, start, end) <= Decimal("4.5")
