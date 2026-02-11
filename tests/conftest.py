import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cti.core.database import get_db
from cti.core.security import create_access_token, hash_password
from cti.main import app
from cti.models.base import Base
from cti.models.user import User, UserRole

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@test.local",
        hashed_password=hash_password("adminpassword"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def analyst_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username="analyst",
        email="analyst@test.local",
        hashed_password=hash_password("analystpassword"),
        role=UserRole.analyst,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def readonly_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        username="viewer",
        email="viewer@test.local",
        hashed_password=hash_password("viewerpassword"),
        role=UserRole.readonly,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def analyst_headers(analyst_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(analyst_user.id), "role": "analyst"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def readonly_headers(readonly_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(readonly_user.id), "role": "readonly"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
