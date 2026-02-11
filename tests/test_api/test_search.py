import pytest
from httpx import AsyncClient

from cti.models.user import User


@pytest.mark.asyncio
async def test_search_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/search?q=test")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.get("/api/v1/search", headers=analyst_headers)
    assert response.status_code == 422
