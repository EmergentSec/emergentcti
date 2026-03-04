"""Async SQLAlchemy engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from cti.core.config import get_settings

# ── Async engine + session (application) ─────────────────────────────────

settings = get_settings()

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine + session (Alembic migrations) ──────────────────────────

sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

sync_session_factory = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


# ── FastAPI dependency ───────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session; commit on success, rollback on error."""
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
