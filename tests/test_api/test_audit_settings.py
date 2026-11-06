"""Audit events for API keys, users and global settings (issue #16, task T4)."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from cti.core.dependencies import get_current_auth
from cti.models.api_key import ApiKey
from cti.models.audit import AuditEvent
from cti.models.user import User, UserRole
from cti.services.auth_service import hash_password
from tests.policy_helpers import non_admin_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

SETTINGS = "/api/v1/settings"
MISSING = "00000000-0000-0000-0000-000000000000"
PASSWORD = "sentinel original passphrase"
NEW_PASSWORD = "sentinel replacement passphrase"
EMAIL = "sentinel-mail@example.org"


async def events(db: AsyncSession, action: str | None = None) -> list[AuditEvent]:
    db.expunge_all()
    query = select(AuditEvent).order_by(AuditEvent.occurred_at, AuditEvent.id)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    return list((await db.scalars(query)).all())


async def rows_json(db: AsyncSession) -> str:
    rows = (await db.execute(select(AuditEvent.__table__))).all()
    return json.dumps([list(row) for row in rows], default=str)


def assert_not_succeeded(found: list[AuditEvent]) -> None:
    assert found, "expected a failed/denied event"
    assert all(e.outcome != "succeeded" for e in found)


async def make_user(
    db: AsyncSession, username: str, role: UserRole = UserRole.user, **kwargs: object
) -> tuple[uuid.UUID, str]:
    password_hash = await hash_password(PASSWORD)
    user = User(username=username, password_hash=password_hash, role=role, **kwargs)
    db.add(user)
    await db.commit()
    return user.id, password_hash


@asynccontextmanager
async def as_user(
    app: FastAPI, db: AsyncSession, user_id: uuid.UUID
) -> AsyncGenerator[AsyncClient, None]:
    """A client authenticated as an existing database user."""

    async def _auth() -> User:
        user = await db.get(User, user_id)
        assert user is not None
        return user

    app.dependency_overrides[get_current_auth] = _auth
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_auth, None)


# ── API keys ───────────────────────────────────────────────────────────────


async def test_api_key_create_never_stores_the_raw_key(client: AsyncClient, db_session) -> None:
    response = await client.post(f"{SETTINGS}/api-keys", json={"name": "Firewall"})
    assert response.status_code == 201
    body = response.json()
    raw_key = body["key"]
    [event] = await events(db_session, "api_key.create")
    assert (event.outcome, event.resource_type, event.resource_id, event.resource_label) == (
        "succeeded",
        "api_key",
        body["id"],
        "Firewall",
    )
    assert (event.actor_type, event.actor_label) == ("api_key", "Test Key")
    record = await db_session.get(ApiKey, uuid.UUID(body["id"]))
    dumped = await rows_json(db_session)
    assert raw_key not in dumped
    assert record.key_hash not in dumped
    assert record.key_prefix not in dumped


async def test_api_key_create_by_non_admin_is_denied(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    async with non_admin_client(app) as user:
        response = await user.post(f"{SETTINGS}/api-keys", json={"name": "Sneaky"})
    assert response.status_code == 403
    found = await events(db_session, "api_key.create")
    assert_not_succeeded(found)
    assert found[0].outcome == "denied"
    assert (await db_session.scalars(select(ApiKey.name))).all() == ["Test Key"]


async def test_api_key_revoke_records_record_id(client: AsyncClient, db_session) -> None:
    created = (await client.post(f"{SETTINGS}/api-keys", json={"name": "Old"})).json()
    assert (await client.delete(f"{SETTINGS}/api-keys/{created['id']}")).status_code == 204
    [event] = await events(db_session, "api_key.revoke")
    assert (event.outcome, event.resource_id, event.resource_label) == (
        "succeeded",
        created["id"],
        "Old",
    )
    assert event.summary == {"is_active": {"before": True, "after": False}}
    assert created["key"] not in await rows_json(db_session)


async def test_api_key_revoke_failures_are_recorded(client: AsyncClient, db_session) -> None:
    assert (await client.delete(f"{SETTINGS}/api-keys/{MISSING}")).status_code == 404
    own = await db_session.scalar(select(ApiKey.id).where(ApiKey.name == "Test Key"))
    assert (await client.delete(f"{SETTINGS}/api-keys/{own}")).status_code == 400
    found = await events(db_session, "api_key.revoke")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_id, e.resource_label, e.summary) for e in found] == [
        ("failed", MISSING, None, {"reason": "not_found", "status": 404}),
        ("failed", str(own), "Test Key", {"reason": "self_revocation", "status": 400}),
    ]
    assert await db_session.scalar(select(ApiKey.is_active).where(ApiKey.id == own)) is True


# ── users ──────────────────────────────────────────────────────────────────


async def test_user_create_records_role_never_password(client: AsyncClient, db_session) -> None:
    response = await client.post(
        f"{SETTINGS}/users",
        json={"username": "carol", "password": PASSWORD, "role": "admin", "email": EMAIL},
    )
    assert response.status_code == 201
    [event] = await events(db_session, "user.create")
    assert (event.outcome, event.resource_id, event.resource_label) == (
        "succeeded",
        response.json()["id"],
        "carol",
    )
    assert event.summary == {"role": "admin", "is_active": True}
    password_hash = await db_session.scalar(select(User.password_hash))
    dumped = await rows_json(db_session)
    assert PASSWORD not in dumped
    assert password_hash not in dumped
    assert EMAIL not in dumped


async def test_user_create_duplicate_records_failed(client: AsyncClient, db_session) -> None:
    await make_user(db_session, "carol")
    response = await client.post(
        f"{SETTINGS}/users", json={"username": "carol", "password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    found = await events(db_session, "user.create")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_label, e.summary) for e in found] == [
        ("failed", "carol", {"reason": "username_taken", "status": 400})
    ]
    assert NEW_PASSWORD not in await rows_json(db_session)


async def test_user_update_records_role_and_active_before_after(
    client: AsyncClient, db_session
) -> None:
    user_id, _ = await make_user(db_session, "carol")
    response = await client.put(
        f"{SETTINGS}/users/{user_id}",
        json={"role": "admin", "is_active": False, "email": EMAIL},
    )
    assert response.status_code == 200
    [event] = await events(db_session, "user.update")
    assert (event.outcome, event.resource_id, event.resource_label) == (
        "succeeded",
        str(user_id),
        "carol",
    )
    assert event.summary == {
        "changed_fields": ["email", "is_active", "role"],
        "role": {"before": "user", "after": "admin"},
        "is_active": {"before": True, "after": False},
    }
    assert EMAIL not in await rows_json(db_session)


async def test_user_update_last_admin_refusal_records_failed(
    client: AsyncClient, db_session
) -> None:
    admin_id, _ = await make_user(db_session, "alice", role=UserRole.admin)
    response = await client.put(f"{SETTINGS}/users/{admin_id}", json={"role": "user"})
    assert response.status_code == 400
    found = await events(db_session, "user.update")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_label, e.summary) for e in found] == [
        ("failed", "alice", {"reason": "last_admin", "status": 400})
    ]
    assert await db_session.scalar(select(User.role).where(User.id == admin_id)) == UserRole.admin


async def test_user_delete_last_admin_refusal_records_failed(
    client: AsyncClient, db_session
) -> None:
    admin_id, _ = await make_user(db_session, "alice", role=UserRole.admin)
    assert (await client.delete(f"{SETTINGS}/users/{admin_id}")).status_code == 400
    found = await events(db_session, "user.delete")
    assert_not_succeeded(found)
    assert found[0].summary == {"reason": "last_admin", "status": 400}
    assert await db_session.get(User, admin_id) is not None


async def test_user_delete_keeps_that_users_actor_events(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    user_id, _ = await make_user(db_session, "carol")
    async with as_user(app, db_session, user_id) as carol:
        response = await carol.put(
            f"{SETTINGS}/users/{user_id}/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        )
    assert response.status_code == 204
    assert (await client.delete(f"{SETTINGS}/users/{user_id}")).status_code == 204

    assert await db_session.get(User, user_id) is None
    [deleted] = await events(db_session, "user.delete")
    assert (deleted.outcome, deleted.resource_id, deleted.resource_label) == (
        "succeeded",
        str(user_id),
        "carol",
    )
    assert deleted.summary == {"role": "user", "is_active": True}
    by_carol = [e for e in await events(db_session) if e.actor_id == str(user_id)]
    assert [(e.action, e.actor_type, e.actor_label) for e in by_carol] == [
        ("user.password_change", "user", "carol")
    ]


async def test_password_change_records_no_secret(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    user_id, _ = await make_user(db_session, "carol")
    response = await client.put(
        f"{SETTINGS}/users/{user_id}/password", json={"new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204
    [event] = await events(db_session, "user.password_change")
    assert (event.outcome, event.resource_id, event.resource_label, event.summary) == (
        "succeeded",
        str(user_id),
        "carol",
        {"self_service": False},
    )
    new_hash = await db_session.scalar(select(User.password_hash).where(User.id == user_id))
    dumped = await rows_json(db_session)
    assert NEW_PASSWORD not in dumped
    assert new_hash not in dumped


async def test_password_change_for_another_user_is_denied(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    carol_id, _ = await make_user(db_session, "carol")
    dave_id, dave_hash = await make_user(db_session, "dave")
    async with as_user(app, db_session, carol_id) as carol:
        response = await carol.put(
            f"{SETTINGS}/users/{dave_id}/password", json={"new_password": NEW_PASSWORD}
        )
    assert response.status_code == 403
    found = await events(db_session, "user.password_change")
    assert_not_succeeded(found)
    assert [(e.outcome, e.actor_label, e.resource_id, e.summary) for e in found] == [
        (
            "denied",
            "carol",
            str(dave_id),
            {"self_service": False, "reason": "not_permitted", "status": 403},
        )
    ]
    assert await db_session.scalar(select(User.password_hash).where(User.id == dave_id)) == (
        dave_hash
    )


async def test_password_change_with_wrong_current_password_records_failed(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    user_id, _ = await make_user(db_session, "carol")
    async with as_user(app, db_session, user_id) as carol:
        response = await carol.put(
            f"{SETTINGS}/users/{user_id}/password",
            json={"current_password": "sentinel wrong passphrase", "new_password": NEW_PASSWORD},
        )
    assert response.status_code == 400
    found = await events(db_session, "user.password_change")
    assert_not_succeeded(found)
    assert found[0].summary == {
        "self_service": True,
        "reason": "current_password_incorrect",
        "status": 400,
    }
    dumped = await rows_json(db_session)
    assert "sentinel wrong passphrase" not in dumped
    assert NEW_PASSWORD not in dumped


# ── settings ───────────────────────────────────────────────────────────────


async def test_settings_config_is_read_only(app: FastAPI, client: AsyncClient, db_session) -> None:
    # Config comes from the environment (.env + restart); there is no write route,
    # so a PUT is a 405 for anyone and nothing is audited.
    response = await client.put(f"{SETTINGS}/config", json={"instance_name": "x"})
    assert response.status_code == 405
    async with non_admin_client(app) as user:
        assert (
            await user.put(f"{SETTINGS}/config", json={"instance_name": "x"})
        ).status_code == 405
    assert (await client.get(f"{SETTINGS}/config")).status_code == 200
    assert await events(db_session) == []
