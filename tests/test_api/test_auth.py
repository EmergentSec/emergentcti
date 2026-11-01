"""Test auth endpoints, role enforcement, and user self-service guards."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import timezone

import bcrypt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core import redis as redis_module
from cti.core.config import get_settings
from cti.models.refresh_token import RefreshToken
from cti.models.user import User, UserRole
from cti.services.auth_service import decode_access_token

JWT_SECRET = "test-jwt-secret-key-with-enough-length-for-hs256"  # gitleaks:allow
PASSWORD = "correct-horse-battery"


class FakeRedis:
    """Minimal in-memory stand-in covering what the login rate limiter uses."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def pipeline(self) -> FakeRedis:
        return self

    async def __aenter__(self) -> FakeRedis:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def incr(self, key: str) -> None:
        self.store[key] = str(int(self.store.get(key, "0")) + 1)

    def expire(self, key: str, seconds: int, nx: bool = False) -> None:  # noqa: ARG002
        return None

    async def execute(self) -> None:
        return None


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """The app lifespan (and so init_redis) does not run under ASGITransport."""
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "_redis_client", fake)
    return fake


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the settings the lifespan would normally validate/generate."""
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr(JWT_SECRET))
    # Non-development marks cookies Secure, which httpx will not send over http://
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)


@pytest.fixture(autouse=True)
def sqlite_aware_expiry() -> Generator[None, None, None]:
    """verify_refresh_token compares expires_at to an aware "now". Postgres
    returns timestamptz as aware; SQLite hands back naive values, so tag
    them as UTC on load (test-DB shim).
    """

    def tag_utc(target: RefreshToken, *_: object) -> None:
        expires_at = target.__dict__.get("expires_at")
        if expires_at is not None and expires_at.tzinfo is None:
            target.__dict__["expires_at"] = expires_at.replace(tzinfo=timezone.utc)

    event.listen(RefreshToken, "load", tag_utc)
    event.listen(RefreshToken, "refresh", tag_utc)
    yield
    event.remove(RefreshToken, "load", tag_utc)
    event.remove(RefreshToken, "refresh", tag_utc)


async def _make_user(
    db: AsyncSession,
    username: str,
    role: UserRole = UserRole.user,
    is_active: bool = True,
) -> User:
    # Low bcrypt cost keeps the suite fast; verify_password accepts any cost.
    password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    user = User(username=username, password_hash=password_hash, role=role, is_active=is_active)
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, "alice", role=UserRole.admin)


@pytest.fixture
async def normal_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, "bob", role=UserRole.user)


@pytest.fixture
async def anon(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Client with no credentials (the shared ``client`` fixture sends an API key)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _login(ac: AsyncClient, username: str, password: str = PASSWORD):
    return await ac.post("/api/v1/auth/login", json={"username": username, "password": password})


# ── Login ─────────────────────────────────────────────────────────────


async def test_login_success_sets_cookies_and_returns_user(
    anon: AsyncClient, admin_user: User
) -> None:
    response = await _login(anon, "alice")
    assert response.status_code == 200
    assert response.json() == {"id": str(admin_user.id), "username": "alice", "role": "admin"}

    set_cookies = response.headers.get_list("set-cookie")
    access = next(c for c in set_cookies if c.startswith("access_token="))
    refresh = next(c for c in set_cookies if c.startswith("refresh_token="))
    assert "HttpOnly" in access and "Path=/api" in access
    assert "HttpOnly" in refresh and "Path=/api/v1/auth/" in refresh

    payload = decode_access_token(response.cookies["access_token"], JWT_SECRET)
    assert payload["sub"] == str(admin_user.id)
    assert payload["role"] == "admin"


async def test_login_wrong_password_returns_401(anon: AsyncClient, admin_user: User) -> None:
    response = await _login(anon, "alice", "not-the-password")
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


async def test_login_unknown_user_returns_401(anon: AsyncClient) -> None:
    response = await _login(anon, "nobody")
    assert response.status_code == 401


async def test_login_rate_limited_after_five_failures(
    app: FastAPI, anon: AsyncClient, admin_user: User
) -> None:
    for _ in range(5):
        response = await _login(anon, "alice", "not-the-password")
        assert response.status_code == 401

    # Sixth attempt is blocked even with the correct password.
    response = await _login(anon, "alice")
    assert response.status_code == 429

    # The counter is per client IP: another address is unaffected.
    transport = ASGITransport(app=app, client=("10.0.0.2", 1234))
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        response = await _login(other, "alice")
        assert response.status_code == 200


async def test_successful_login_clears_failure_counter(
    anon: AsyncClient, admin_user: User, fake_redis: FakeRedis
) -> None:
    for _ in range(4):
        await _login(anon, "alice", "not-the-password")
    assert (await _login(anon, "alice")).status_code == 200
    assert fake_redis.store == {}


async def test_login_inactive_user_rejected(anon: AsyncClient, db_session: AsyncSession) -> None:
    await _make_user(db_session, "carol", is_active=False)
    response = await _login(anon, "carol")
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


# ── Refresh / logout ──────────────────────────────────────────────────


async def test_refresh_issues_new_access_cookie(anon: AsyncClient, admin_user: User) -> None:
    login = await _login(anon, "alice")
    old_refresh = login.cookies["refresh_token"]

    # Drop the access cookie so only the refresh token can restore the session.
    anon.cookies.delete("access_token")
    assert (await anon.get("/api/v1/auth/me")).status_code == 401

    response = await anon.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    payload = decode_access_token(response.cookies["access_token"], JWT_SECRET)
    assert payload["sub"] == str(admin_user.id)
    assert response.cookies["refresh_token"] != old_refresh  # rotated

    assert (await anon.get("/api/v1/auth/me")).status_code == 200


async def test_refresh_without_cookie_returns_401(anon: AsyncClient) -> None:
    response = await anon.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_rotated_refresh_token_cannot_be_reused(
    anon: AsyncClient, admin_user: User
) -> None:
    login = await _login(anon, "alice")
    old_refresh = login.cookies["refresh_token"]
    assert (await anon.post("/api/v1/auth/refresh")).status_code == 200

    anon.cookies.clear()
    response = await anon.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_refresh}"}
    )
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(
    anon: AsyncClient, admin_user: User, db_session: AsyncSession
) -> None:
    login = await _login(anon, "alice")
    raw_refresh = login.cookies["refresh_token"]

    response = await anon.post("/api/v1/auth/logout")
    assert response.status_code == 200
    # Both cookies are expired in the client.
    assert "access_token" not in anon.cookies
    assert "refresh_token" not in anon.cookies

    tokens = (await db_session.execute(select(RefreshToken))).scalars().all()
    assert [t.revoked for t in tokens] == [True]

    # Replaying the captured token server-side must fail, not just lack a cookie.
    response = await anon.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={raw_refresh}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


# ── /auth/me ──────────────────────────────────────────────────────────


async def test_me_for_cookie_user(anon: AsyncClient, normal_user: User) -> None:
    await _login(anon, "bob")
    response = await anon.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {
        "type": "user", "id": str(normal_user.id), "name": "bob", "role": "user",
    }


async def test_me_for_api_key(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "api_key"
    assert data["name"] == "Test Key"
    assert data["role"] == "admin"


async def test_me_unauthenticated_returns_401(anon: AsyncClient) -> None:
    response = await anon.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_deactivated_user_cookie_rejected(
    anon: AsyncClient, normal_user: User, db_session: AsyncSession
) -> None:
    await _login(anon, "bob")
    assert (await anon.get("/api/v1/auth/me")).status_code == 200

    normal_user.is_active = False
    await db_session.commit()

    # A still-valid access token stops working, and it cannot be refreshed.
    assert (await anon.get("/api/v1/auth/me")).status_code == 401
    assert (await anon.post("/api/v1/auth/refresh")).status_code == 401


# ── Role enforcement ──────────────────────────────────────────────────


async def test_user_role_forbidden_on_admin_endpoint(
    anon: AsyncClient, normal_user: User
) -> None:
    await _login(anon, "bob")
    response = await anon.get("/api/v1/settings/users")
    assert response.status_code == 403


async def test_admin_role_allowed_on_admin_endpoint(anon: AsyncClient, admin_user: User) -> None:
    await _login(anon, "alice")
    response = await anon.get("/api/v1/settings/users")
    assert response.status_code == 200
    assert [u["username"] for u in response.json()] == ["alice"]


async def test_api_key_allowed_on_admin_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/users")
    assert response.status_code == 200


# ── Password change ───────────────────────────────────────────────────


async def test_self_password_change_requires_current_password(
    anon: AsyncClient, normal_user: User
) -> None:
    await _login(anon, "bob")
    url = f"/api/v1/settings/users/{normal_user.id}/password"
    new_password = "a-brand-new-passphrase"

    response = await anon.put(url, json={"new_password": new_password})
    assert response.status_code == 400

    response = await anon.put(
        url, json={"new_password": new_password, "current_password": "not-the-password"}
    )
    assert response.status_code == 400

    # Neither rejected attempt changed the password.
    assert (await _login(anon, "bob")).status_code == 200

    response = await anon.put(
        url, json={"new_password": new_password, "current_password": PASSWORD}
    )
    assert response.status_code == 204

    assert (await _login(anon, "bob")).status_code == 401
    assert (await _login(anon, "bob", new_password)).status_code == 200


async def test_admin_self_password_change_requires_current_password(
    anon: AsyncClient, admin_user: User, normal_user: User
) -> None:
    await _login(anon, "alice")
    own_url = f"/api/v1/settings/users/{admin_user.id}/password"
    new_password = "a-brand-new-passphrase"

    response = await anon.put(
        own_url, json={"new_password": new_password, "current_password": "not-the-password"}
    )
    assert response.status_code == 400

    # Resetting someone else's password still needs no current password.
    response = await anon.put(
        f"/api/v1/settings/users/{normal_user.id}/password",
        json={"new_password": new_password},
    )
    assert response.status_code == 204


async def test_self_password_change_keeps_current_session_only(
    app: FastAPI, anon: AsyncClient, normal_user: User
) -> None:
    await _login(anon, "bob")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _login(other, "bob")

        response = await anon.put(
            f"/api/v1/settings/users/{normal_user.id}/password",
            json={"new_password": "a-brand-new-passphrase", "current_password": PASSWORD},
        )
        assert response.status_code == 204

        # The session that made the change can still refresh; the other cannot.
        assert (await anon.post("/api/v1/auth/refresh")).status_code == 200
        assert (await other.post("/api/v1/auth/refresh")).status_code == 401


async def test_admin_reset_revokes_target_users_sessions(
    app: FastAPI, anon: AsyncClient, admin_user: User, normal_user: User
) -> None:
    await _login(anon, "alice")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await _login(other, "bob")

        response = await anon.put(
            f"/api/v1/settings/users/{normal_user.id}/password",
            json={"new_password": "a-brand-new-passphrase"},
        )
        assert response.status_code == 204
        assert (await other.post("/api/v1/auth/refresh")).status_code == 401


async def test_user_cannot_change_another_users_password(
    anon: AsyncClient, normal_user: User, admin_user: User
) -> None:
    await _login(anon, "bob")
    response = await anon.put(
        f"/api/v1/settings/users/{admin_user.id}/password",
        json={"new_password": "a-brand-new-passphrase", "current_password": PASSWORD},
    )
    assert response.status_code == 403


# ── Admin self-protection ─────────────────────────────────────────────


async def test_admin_cannot_delete_self(
    anon: AsyncClient, admin_user: User, db_session: AsyncSession
) -> None:
    # A second admin, so the last-admin guard is not what blocks the request.
    await _make_user(db_session, "dave", role=UserRole.admin)
    await _login(anon, "alice")

    response = await anon.delete(f"/api/v1/settings/users/{admin_user.id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot delete your own account"
    assert (await anon.get("/api/v1/auth/me")).status_code == 200


async def test_admin_cannot_deactivate_self(
    anon: AsyncClient, admin_user: User, db_session: AsyncSession
) -> None:
    await _make_user(db_session, "dave", role=UserRole.admin)
    await _login(anon, "alice")

    response = await anon.put(
        f"/api/v1/settings/users/{admin_user.id}", json={"is_active": False}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot deactivate your own account"
    assert (await anon.get("/api/v1/auth/me")).status_code == 200
