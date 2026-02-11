import pytest
from httpx import AsyncClient

from cti.models.user import User


@pytest.mark.asyncio
async def test_create_observable_ip(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={
            "type": "ip-addr",
            "value": "192.168.1.1",
            "confidence_score": 80,
            "tlp": "amber",
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "ip-addr"
    assert data["value"] == "192.168.1.1"
    assert data["confidence_score"] == 80


@pytest.mark.asyncio
async def test_create_observable_domain(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={"type": "domain-name", "value": "malware.example.com"},
        headers=analyst_headers,
    )
    assert response.status_code == 201
    assert response.json()["value"] == "malware.example.com"


@pytest.mark.asyncio
async def test_create_observable_hash(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    sha256 = "a" * 64
    response = await client.post(
        "/api/v1/observables",
        json={"type": "file-hash", "value": sha256},
        headers=analyst_headers,
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_observable_invalid_ip(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "999.999.999.999"},
        headers=analyst_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_observable_invalid_hash(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={"type": "file-hash", "value": "tooshort"},
        headers=analyst_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_observable_readonly_forbidden(client: AsyncClient, readonly_user: User, readonly_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "10.0.0.1"},
        headers=readonly_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_observables(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    # Create a few
    for i in range(3):
        await client.post(
            "/api/v1/observables",
            json={"type": "ip-addr", "value": f"10.0.0.{i+1}"},
            headers=analyst_headers,
        )

    response = await client.get("/api/v1/observables", headers=analyst_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_list_observables_filter_by_type(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "1.2.3.4"},
        headers=analyst_headers,
    )
    await client.post(
        "/api/v1/observables",
        json={"type": "domain-name", "value": "example.com"},
        headers=analyst_headers,
    )

    response = await client.get(
        "/api/v1/observables?type=ip-addr", headers=analyst_headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["type"] == "ip-addr"


@pytest.mark.asyncio
async def test_get_observable(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    create_resp = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "8.8.8.8"},
        headers=analyst_headers,
    )
    obs_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/observables/{obs_id}", headers=analyst_headers)
    assert response.status_code == 200
    assert response.json()["value"] == "8.8.8.8"


@pytest.mark.asyncio
async def test_update_observable(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    create_resp = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "8.8.4.4", "confidence_score": 50},
        headers=analyst_headers,
    )
    obs_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/observables/{obs_id}",
        json={"confidence_score": 90, "tlp": "red"},
        headers=analyst_headers,
    )
    assert response.status_code == 200
    assert response.json()["confidence_score"] == 90
    assert response.json()["tlp"] == "red"


@pytest.mark.asyncio
async def test_delete_observable_admin(client: AsyncClient, admin_user: User, admin_headers: dict):
    # Admin creates and deletes
    create_resp = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "172.16.0.1"},
        headers=admin_headers,
    )
    obs_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/observables/{obs_id}", headers=admin_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_observable_analyst_forbidden(
    client: AsyncClient, analyst_user: User, analyst_headers: dict
):
    create_resp = await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "172.16.0.2"},
        headers=analyst_headers,
    )
    obs_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/observables/{obs_id}", headers=analyst_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_observable_dedup(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    # Create same observable twice - should upsert
    await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "203.0.113.1", "confidence_score": 50},
        headers=analyst_headers,
    )
    await client.post(
        "/api/v1/observables",
        json={"type": "ip-addr", "value": "203.0.113.1", "confidence_score": 80},
        headers=analyst_headers,
    )

    response = await client.get(
        "/api/v1/observables?value=203.0.113.1", headers=analyst_headers
    )
    data = response.json()
    # Should have exactly 1
    matching = [i for i in data["items"] if i["value"] == "203.0.113.1"]
    assert len(matching) == 1
    # Confidence should be the higher value
    assert matching[0]["confidence_score"] == 80


@pytest.mark.asyncio
async def test_observable_stats(client: AsyncClient, analyst_user: User, analyst_headers: dict):
    response = await client.get("/api/v1/observables/stats", headers=analyst_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "by_type" in data
