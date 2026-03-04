"""Test export endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_blocklist_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export/blocklist/ip-addr")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == ""


@pytest.mark.asyncio
async def test_json_export_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export/json")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["observables"] == []


@pytest.mark.asyncio
async def test_text_export_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/export/text")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
