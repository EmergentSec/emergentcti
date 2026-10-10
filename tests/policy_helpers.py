"""Shared helpers for allowlist / export profile tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.dependencies import get_current_auth
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.models.user import User, UserRole


async def add_feed(db: AsyncSession, name: str = "Feed A", **kwargs: object) -> Feed:
    feed = Feed(name=name, feed_type=FeedType.FILE, **kwargs)
    db.add(feed)
    await db.commit()
    return feed


async def add_observable(
    db: AsyncSession,
    value: str,
    obs_type: ObservableType = ObservableType.IP_ADDR,
    confidence: int = 80,
    last_seen: datetime | None = None,
    feed: Feed | None = None,
) -> Observable:
    now = datetime.now(UTC)
    obs = Observable(
        id=uuid.uuid4(),
        type=obs_type,
        value=value,
        confidence_score=confidence,
        first_seen=last_seen or now,
        last_seen=last_seen or now,
    )
    db.add(obs)
    await db.flush()
    if feed is not None:
        db.add(
            ObservableSource(
                observable_id=obs.id,
                feed_id=feed.id,
                source_confidence=confidence,
                native_confidence=confidence,
            )
        )
    await db.commit()
    return obs


async def allow(
    client: AsyncClient,
    kind: str,
    value: str,
    observable_type: str | None = None,
    reason: str = "known good",
) -> dict:
    body: dict = {"kind": kind, "value": value, "reason": reason}
    if observable_type is not None:
        body["observable_type"] = observable_type
    response = await client.post("/api/v1/allowlist", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@asynccontextmanager
async def non_admin_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """An authenticated client whose subject is a regular (non-admin) user."""
    user = User(id=uuid.uuid4(), username="bob", password_hash="x", role=UserRole.user)

    async def _auth() -> User:
        return user

    app.dependency_overrides[get_current_auth] = _auth
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_auth, None)
