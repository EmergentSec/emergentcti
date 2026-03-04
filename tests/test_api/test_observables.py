"""Test observable endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_observables_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/observables")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_observables_with_filters(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/observables",
        params={"type": "ip-addr", "confidence_min": 50, "page": 1, "size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_observable_not_found(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/observables/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
