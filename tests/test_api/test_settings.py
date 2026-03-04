"""Test settings/API key endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/api-keys")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least the seeded test key


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/settings/api-keys",
        json={"name": "Test Key 2", "description": "For testing"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "key" in data  # Full key shown at creation
    assert data["name"] == "Test Key 2"
    assert data["key"].startswith("cti_")


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/config")
    assert response.status_code == 200
    data = response.json()
    assert "confidence_decay_enabled" in data


@pytest.mark.asyncio
async def test_unauthorized_without_key(client: AsyncClient) -> None:
    # Remove the API key header
    client.headers.pop("X-API-Key", None)
    response = await client.get("/api/v1/settings/api-keys")
    assert response.status_code == 401
