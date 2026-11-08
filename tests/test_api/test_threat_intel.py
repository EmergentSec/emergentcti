"""API tests for threat-intel skills and dual model roles."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from cti.core.dependencies import get_current_auth
from cti.models.user import User, UserRole

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

AI_BASE = "/api/v1/settings/ai"
TI_BASE = "/api/v1/threat-intel"
FAKE_KEY = "sk-test-not-a-real-key-0000"


@pytest.fixture
async def ordinary_user(db_session: AsyncSession) -> User:
    user = User(
        username="ti-user",
        password_hash="unused",
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def ordinary_client(
    app: FastAPI,
    ordinary_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate_as_user() -> User:
        return ordinary_user

    app.dependency_overrides[get_current_auth] = authenticate_as_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


async def test_skills_require_admin(ordinary_client: AsyncClient) -> None:
    response = await ordinary_client.get(f"{TI_BASE}/skills")
    assert response.status_code == 403


async def test_list_and_get_skills(client: AsyncClient) -> None:
    listed = await client.get(f"{TI_BASE}/skills")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert "threat_researcher" in ids
    assert "threat_report_writer" in ids

    detail = await client.get(f"{TI_BASE}/skills/threat_researcher")
    assert detail.status_code == 200
    body = detail.json()["content"].casefold()
    assert "anna" not in body
    assert "defensive" in body


async def test_set_research_and_writer_roles(client: AsyncClient) -> None:
    save = await client.put(
        f"{AI_BASE}/providers/openai",
        json={"api_key": FAKE_KEY},
    )
    assert save.status_code == 200

    research = await client.put(
        f"{AI_BASE}/roles/research",
        json={"provider": "openai", "model": "gpt-research", "is_custom": True},
    )
    assert research.status_code == 200, research.text
    assert research.json() == {
        "provider": "openai",
        "model": "gpt-research",
        "is_custom": True,
    }

    writer = await client.put(
        f"{AI_BASE}/roles/writer",
        json={"provider": "openai", "model": "gpt-writer", "is_custom": True},
    )
    assert writer.status_code == 200, writer.text

    settings = await client.get(AI_BASE)
    assert settings.status_code == 200
    payload = settings.json()
    assert payload["roles"]["research"]["model"] == "gpt-research"
    assert payload["roles"]["writer"]["model"] == "gpt-writer"

    cleared = await client.delete(f"{AI_BASE}/roles/research")
    assert cleared.status_code == 204
    settings = await client.get(AI_BASE)
    assert settings.json()["roles"]["research"] is None
    assert settings.json()["roles"]["writer"]["model"] == "gpt-writer"


async def test_generate_report_requires_roles(client: AsyncClient) -> None:
    response = await client.post(
        f"{TI_BASE}/generate-report",
        json={
            "item": {"title": "Example", "link": "https://example.com", "severity": "HIGH"},
            "environment": "homelab",
        },
    )
    assert response.status_code == 409
    assert response.json()["category"] == "not_configured"


async def test_fetch_reports_unwritable_data_dir(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    def deny(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied", "data")

    monkeypatch.setattr(Path, "mkdir", deny)
    response = await client.post(f"{TI_BASE}/fetch")
    assert response.status_code == 500
    assert "THREAT_INTEL_DATA_DIR" in response.json()["detail"]
