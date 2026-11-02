"""External-AI outbound preview endpoint tests (#17)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from cti.core.dependencies import get_current_auth
from cti.models.report import Report, ReportOrigin
from cti.models.user import User, UserRole

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

ENDPOINT = "/api/v1/ai/outbound/preview"


@pytest.fixture
async def analyst(db_session: AsyncSession) -> User:
    user = User(username="api-outbound-analyst", password_hash="x", role=UserRole.user)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(username="api-outbound-admin", password_hash="x", role=UserRole.admin)
    db_session.add(user)
    await db_session.commit()
    return user


async def _user_client(app: FastAPI, user: User) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate() -> User:
        return user

    app.dependency_overrides[get_current_auth] = authenticate
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_current_auth, None)


@pytest.fixture
async def analyst_client(app: FastAPI, analyst: User) -> AsyncGenerator[AsyncClient, None]:
    async for client in _user_client(app, analyst):
        yield client


@pytest.fixture
async def admin_client(app: FastAPI, admin: User) -> AsyncGenerator[AsyncClient, None]:
    async for client in _user_client(app, admin):
        yield client


@pytest.fixture
async def report(db_session: AsyncSession) -> Report:
    item = Report(
        title="API preview report",
        summary="Visible minimized summary",
        origin=ReportOrigin.INTERNAL,
        tlp="green",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


def _request(report: Report) -> dict[str, object]:
    return {
        "provider": "openai",
        "model": "gpt-test",
        "refs": [{"type": "report", "id": str(report.id)}],
    }


async def test_interactive_analyst_can_preview(analyst_client: AsyncClient, report: Report) -> None:
    response = await analyst_client.post(ENDPOINT, json=_request(report))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-test"
    assert body["items"][0]["included"] is True
    assert body["content_chars"] == len(body["content"])
    assert body["digest"].count(".") == 1


async def test_interactive_admin_can_preview(admin_client: AsyncClient, report: Report) -> None:
    response = await admin_client.post(ENDPOINT, json=_request(report))
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["included"] is True


async def test_api_key_auth_is_rejected(client: AsyncClient, report: Report) -> None:
    response = await client.post(ENDPOINT, json=_request(report))
    assert response.status_code == 403
    assert response.json()["detail"] == "Interactive user session required"


async def test_unauthenticated_request_is_401(app: FastAPI, report: Report) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(ENDPOINT, json=_request(report))
    assert response.status_code == 401


async def test_more_than_25_refs_is_422(analyst_client: AsyncClient, report: Report) -> None:
    payload = _request(report)
    payload["refs"] = [
        {"type": "report", "id": f"00000000-0000-0000-0000-{index:012d}"} for index in range(26)
    ]
    response = await analyst_client.post(ENDPOINT, json=payload)
    assert response.status_code == 422


async def test_invalid_provider_and_ref_type_are_422(
    analyst_client: AsyncClient, report: Report
) -> None:
    payload = _request(report)
    payload["provider"] = "unknown"
    payload["refs"] = [{"type": "user", "id": str(report.id)}]
    response = await analyst_client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
