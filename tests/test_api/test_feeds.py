import pytest
from httpx import AsyncClient

from cti.models.user import User


@pytest.mark.asyncio
async def test_create_feed(client: AsyncClient, admin_user: User, admin_headers: dict):
    response = await client.post(
        "/api/v1/feeds",
        json={
            "name": "Test Feed",
            "description": "A test threat feed",
            "feed_type": "api",
            "url": "https://api.example.com/iocs",
            "schedule_cron": "0 */6 * * *",
            "config": {"field_mapping": {"ip": "ip-addr"}},
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Feed"
    assert data["feed_type"] == "api"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_create_feed_analyst_forbidden(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.post(
        "/api/v1/feeds",
        json={
            "name": "Forbidden Feed",
            "feed_type": "api",
        },
        headers=analyst_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_feeds(client: AsyncClient, admin_user: User, admin_headers: dict):
    await client.post(
        "/api/v1/feeds",
        json={"name": "Feed 1", "feed_type": "api"},
        headers=admin_headers,
    )

    response = await client.get("/api/v1/feeds", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_feed(client: AsyncClient, admin_user: User, admin_headers: dict):
    create_resp = await client.post(
        "/api/v1/feeds",
        json={"name": "Get Feed Test", "feed_type": "file"},
        headers=admin_headers,
    )
    feed_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/feeds/{feed_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Get Feed Test"


@pytest.mark.asyncio
async def test_update_feed(client: AsyncClient, admin_user: User, admin_headers: dict):
    create_resp = await client.post(
        "/api/v1/feeds",
        json={"name": "Update Me", "feed_type": "api"},
        headers=admin_headers,
    )
    feed_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/feeds/{feed_id}",
        json={"name": "Updated Name", "enabled": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_feed(client: AsyncClient, admin_user: User, admin_headers: dict):
    create_resp = await client.post(
        "/api/v1/feeds",
        json={"name": "Delete Me", "feed_type": "scraper"},
        headers=admin_headers,
    )
    feed_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/feeds/{feed_id}", headers=admin_headers)
    assert response.status_code == 204

    get_resp = await client.get(f"/api/v1/feeds/{feed_id}", headers=admin_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_cron(client: AsyncClient, admin_user: User, admin_headers: dict):
    response = await client.post(
        "/api/v1/feeds",
        json={
            "name": "Bad Cron Feed",
            "feed_type": "api",
            "schedule_cron": "not a cron",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_feed_runs_empty(client: AsyncClient, admin_user: User, admin_headers: dict):
    create_resp = await client.post(
        "/api/v1/feeds",
        json={"name": "Runs Test Feed", "feed_type": "api"},
        headers=admin_headers,
    )
    feed_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/feeds/{feed_id}/runs", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []
