import pytest
from httpx import AsyncClient

from cti.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_as_admin(client: AsyncClient, admin_headers: dict):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@test.local",
            "password": "newpassword123",
            "role": "analyst",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "analyst"


@pytest.mark.asyncio
async def test_register_forbidden_for_analyst(client: AsyncClient, analyst_headers: dict):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "another",
            "email": "another@test.local",
            "password": "password123",
        },
        headers=analyst_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, admin_user: User, admin_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, admin_user: User):
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "adminpassword"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_generate_api_key(client: AsyncClient, admin_user: User, admin_headers: dict):
    response = await client.post("/api/v1/auth/api-key", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["api_key"].startswith("cti_")
