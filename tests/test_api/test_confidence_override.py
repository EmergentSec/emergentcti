from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from cti.core.dependencies import get_current_auth
from cti.models.observable import Observable, ObservableType
from cti.models.user import User, UserRole

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

MISSING_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def analyst(db_session: AsyncSession) -> User:
    user = User(
        username="override-analyst",
        password_hash="unused",
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(
        username="override-admin",
        password_hash="unused",
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _client_as(app: FastAPI, user: User) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate() -> User:
        return user

    app.dependency_overrides[get_current_auth] = authenticate
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


@pytest.fixture
async def analyst_client(app: FastAPI, analyst: User) -> AsyncGenerator[AsyncClient, None]:
    async for ac in _client_as(app, analyst):
        yield ac


@pytest.fixture
async def admin_client(app: FastAPI, admin: User) -> AsyncGenerator[AsyncClient, None]:
    async for ac in _client_as(app, admin):
        yield ac


@pytest.fixture
async def anonymous_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def observable(db_session: AsyncSession) -> Observable:
    row = Observable(
        type=ObservableType.DOMAIN_NAME,
        value="override.example",
        confidence_score=70,
        manual_confidence=70,
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_override_requires_authentication(
    anonymous_client: AsyncClient,
    observable: Observable,
    method: str,
) -> None:
    response = await anonymous_client.request(
        method,
        f"/api/v1/observables/{observable.id}/confidence-override",
        json={"confidence": 40} if method == "put" else None,
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_override_requires_admin(
    analyst_client: AsyncClient,
    observable: Observable,
    method: str,
) -> None:
    response = await analyst_client.request(
        method,
        f"/api/v1/observables/{observable.id}/confidence-override",
        json={"confidence": 40} if method == "put" else None,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_override_unknown_observable_is_404(
    client: AsyncClient,
    method: str,
) -> None:
    response = await client.request(
        method,
        f"/api/v1/observables/{MISSING_ID}/confidence-override",
        json={"confidence": 40} if method == "put" else None,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("value", [-1, 101, 4.5, True, "40", None])
async def test_override_rejects_invalid_confidence(
    client: AsyncClient,
    observable: Observable,
    value: object,
) -> None:
    response = await client.put(
        f"/api/v1/observables/{observable.id}/confidence-override",
        json={"confidence": value},
    )
    assert response.status_code == 422


async def test_set_and_idempotent_clear_return_fields_and_invalidate(
    admin_client: AsyncClient,
    observable: Observable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cti.api.v1 import observables as observables_api

    invalidate = AsyncMock()
    monkeypatch.setattr(observables_api, "invalidate_observable_caches", invalidate)
    url = f"/api/v1/observables/{observable.id}/confidence-override"

    response = await admin_client.put(url, json={"confidence": 12})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confidence_score"] == 12
    assert body["manual_confidence"] == 70
    assert body["confidence_override"]["value"] == 12
    assert body["confidence_override"]["set_at"]
    assert body["confidence_override"]["set_by"] == "override-admin"

    listed = await admin_client.get("/api/v1/observables")
    assert listed.json()["items"][0]["confidence_override"]["value"] == 12

    first_clear = await admin_client.delete(url)
    assert first_clear.status_code == 200, first_clear.text
    assert first_clear.json()["confidence_score"] == 70
    assert first_clear.json()["confidence_override"] is None
    second_clear = await admin_client.delete(url)
    assert second_clear.status_code == 200, second_clear.text
    assert second_clear.json()["confidence_score"] == 70
    assert second_clear.json()["confidence_override"] is None
    assert invalidate.await_count == 3


async def test_override_set_by_becomes_null_after_user_deletion(
    client: AsyncClient,
    db_session: AsyncSession,
    observable: Observable,
) -> None:
    from cti.services import observable_service

    setter = User(
        username="deleted-setter",
        password_hash="unused",
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(setter)
    await db_session.commit()
    await observable_service.set_confidence_override(
        db_session,
        observable.id,
        22,
        set_by_id=setter.id,
    )
    await db_session.commit()
    observable_id = observable.id
    await db_session.execute(delete(User).where(User.id == setter.id))
    await db_session.commit()
    db_session.expire_all()

    response = await client.get(f"/api/v1/observables/{observable_id}")
    assert response.status_code == 200, response.text
    assert response.json()["confidence_override"]["set_by"] is None
