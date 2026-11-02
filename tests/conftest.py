"""Test fixtures for EmergentCTI."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cti.core.database import get_db
from cti.models import Base
from cti.models.api_key import ApiKey

# Use SQLite for tests (no PostgreSQL dependency)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


# SQLite does not have GREATEST(); register it as a user-defined function so
# that upsert logic using func.greatest() works in tests.
@event.listens_for(engine.sync_engine, "connect")
def _register_sqlite_greatest(dbapi_connection, connection_record):
    dbapi_connection.create_function(
        "greatest",
        -1,
        lambda *args: max((a for a in args if a is not None), default=None),
    )


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture(autouse=True)
def audit_independent_sessions(
    setup_db: None,  # Explicit: tables first, and db_session closed before they drop.
    db_session: AsyncSession,
) -> Generator[None, None, None]:
    """Route ``audit.record_independent`` writes to the test database.

    SQLite (unlike PostgreSQL) allows one writer per database, and API tests
    share ``db_session`` with the app, so a second connection cannot insert
    while a request holds a write (even the autoflushed API-key
    ``last_used_at``). Independent writes therefore run in a SAVEPOINT on the
    shared session's connection: they are visible to ``db_session``, and a
    failure path must roll back *before* recording, as in production.
    Tests proving true independence (own session, survives the caller's
    rollback) use the ``separate_audit_sessions`` fixture instead.

    Deliberately not ``monkeypatch``: requesting it from an autouse fixture
    moves its teardown after other autouse patches (e.g. the API suite's
    ``sync_feed_jobs`` mock) and breaks their LIFO restore order.
    """
    from cti.services import audit

    @asynccontextmanager
    async def shared_connection_session() -> AsyncGenerator[AsyncSession, None]:
        connection = await db_session.connection()
        async with AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session

    previous = audit._session_factory
    audit._session_factory = shared_connection_session
    yield
    audit._session_factory = previous


@pytest.fixture
def separate_audit_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Independent audit writes use their own connection, as in production."""
    from cti.services import audit

    monkeypatch.setattr(audit, "_session_factory", TestSessionFactory)


@pytest.fixture
def test_api_key() -> tuple[str, str]:
    """Generate a test API key. Returns (raw_key, key_hash)."""
    raw_key = f"cti_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


@pytest.fixture
async def seeded_api_key(db_session: AsyncSession, test_api_key: tuple[str, str]) -> str:
    """Create an API key in the DB and return the raw key."""
    raw_key, key_hash = test_api_key
    api_key = ApiKey(
        name="Test Key",
        key_hash=key_hash,
        key_prefix=raw_key[:12],
    )
    db_session.add(api_key)
    await db_session.commit()
    return raw_key


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """Create a test FastAPI app with overridden DB dependency."""
    from cti.main import create_app

    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app: FastAPI, seeded_api_key: str) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated async HTTP client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["X-API-Key"] = seeded_api_key
        yield ac
