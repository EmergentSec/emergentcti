"""Audit coverage for feed configuration and manual triggers."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from sqlalchemy import select

from cti.models.audit import AuditEvent
from cti.models.feed import Feed, FeedType
from cti.models.user import UserRole
from tests.policy_helpers import add_feed, non_admin_client

if TYPE_CHECKING:
    import pytest


async def _events(db, action: str) -> list[AuditEvent]:
    db.expunge_all()
    rows = await db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == action)
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    )
    return list(rows.all())


async def test_feed_create_update_delete_audits_success_failure_and_redacts_auth(
    client, db_session
) -> None:
    secret = "feed-secret-marker"
    create_body = {
        "name": "Audited feed",
        "feed_type": "api",
        "url": "https://example.test/feed",
        "enabled": False,
        "auth_config": {
            "auth_type": "api_key",
            "api_key_header": "X-Feed-Key",
            "api_key_value": secret,
        },
    }
    created = await client.post("/api/v1/feeds", json=create_body)
    assert created.status_code == 201, created.text
    feed_id = created.json()["id"]
    invalid = await client.post(
        "/api/v1/feeds",
        json={
            "name": "Bad auth",
            "feed_type": "api",
            "auth_config": {"auth_type": "unsupported", "api_key_value": secret},
        },
    )
    assert invalid.status_code == 422

    updated = await client.put(
        f"/api/v1/feeds/{feed_id}",
        json={"description": "new description", "default_confidence": 81},
    )
    assert updated.status_code == 200
    missing = uuid.uuid4()
    assert (
        await client.put(f"/api/v1/feeds/{missing}", json={"description": "nope"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/feeds/{feed_id}")).status_code == 204
    assert (await client.delete(f"/api/v1/feeds/{feed_id}")).status_code == 404

    create_ok, create_failed = await _events(db_session, "feed.create")
    update_ok, update_failed = await _events(db_session, "feed.update")
    delete_ok, delete_failed = await _events(db_session, "feed.delete")
    assert (create_ok.resource_id, create_ok.resource_label, create_ok.outcome) == (
        feed_id,
        "Audited feed",
        "succeeded",
    )
    assert create_ok.summary == {
        "changed_fields": ["enabled", "feed_type", "name", "url"]
    }
    assert create_failed.summary == {"reason": "invalid_configuration", "status": 422}
    assert update_ok.summary == {"changed_fields": ["default_confidence", "description"]}
    assert (update_failed.resource_id, update_failed.outcome) == (str(missing), "failed")
    assert (delete_ok.resource_id, delete_ok.resource_label) == (feed_id, "Audited feed")
    assert delete_failed.summary == {"reason": "not_found", "status": 404}
    dumped = json.dumps(
        [
            list(row)
            for row in (await db_session.execute(select(AuditEvent.__table__))).all()
        ],
        default=str,
    )
    assert secret not in dumped
    assert "auth_config" not in dumped


async def test_feed_update_tlp_summary_uses_before_after_not_reason(
    client, app, db_session
) -> None:
    created = await client.post(
        "/api/v1/feeds",
        json={"name": "TLP feed", "feed_type": "file", "enabled": False, "tlp": "red"},
    )
    feed_id = created.json()["id"]
    reason = "analyst free text marker"
    async with non_admin_client(app, UserRole.admin) as admin:
        response = await admin.put(
            f"/api/v1/feeds/{feed_id}",
            json={"tlp": "green", "tlp_change_reason": reason},
        )
    assert response.status_code == 200
    [event] = await _events(db_session, "feed.update")
    assert (event.actor_type, event.actor_label, event.outcome) == ("user", "bob", "succeeded")
    assert event.summary == {"changed_fields": ["tlp"], "before": "red", "after": "green"}
    assert reason not in json.dumps(event.summary)


async def test_api_key_red_feed_declassify_records_denied(client, db_session) -> None:
    feed = await add_feed(db_session, "RED declassify audit", tlp="red")
    response = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"tlp": "green", "tlp_change_reason": "approved declassification"},
    )
    assert response.status_code == 403
    events = await _events(db_session, "feed.update")
    assert all(event.outcome != "succeeded" for event in events)
    [event] = events
    assert event.outcome == "denied"
    assert event.summary == {"reason": "interactive_admin_required", "status": 403}


async def test_api_key_red_feed_delete_records_denied(client, db_session) -> None:
    feed = await add_feed(db_session, "RED delete audit", tlp="red")
    response = await client.delete(f"/api/v1/feeds/{feed.id}")
    assert response.status_code == 403
    events = await _events(db_session, "feed.delete")
    assert all(event.outcome != "succeeded" for event in events)
    [event] = events
    assert event.outcome == "denied"
    assert event.summary == {"reason": "interactive_admin_required", "status": 403}


async def test_feed_update_without_tlp_reason_records_failed(client, db_session) -> None:
    feed = await add_feed(db_session, "TLP reason audit", tlp="amber")
    response = await client.put(f"/api/v1/feeds/{feed.id}", json={"tlp": "green"})
    assert response.status_code == 422
    events = await _events(db_session, "feed.update")
    assert all(event.outcome != "succeeded" for event in events)
    assert [event.summary for event in events] == [
        {"reason": "tlp_reason_required", "status": 422}
    ]


async def test_feed_delete_in_use_records_failed(client, db_session) -> None:
    feed = await add_feed(db_session, "Referenced feed audit")
    created = await client.post(
        "/api/v1/export/profiles",
        json={"name": "Feed reference", "format": "text", "feed_id": str(feed.id)},
    )
    assert created.status_code == 201
    response = await client.delete(f"/api/v1/feeds/{feed.id}")
    assert response.status_code == 409
    events = await _events(db_session, "feed.delete")
    assert all(event.outcome != "succeeded" for event in events)
    assert [event.summary for event in events] == [{"reason": "in_use", "status": 409}]


async def test_preconfigured_feed_delete_records_failed(client, db_session) -> None:
    feed = Feed(
        name="Preconfigured audit",
        feed_type=FeedType.FILE,
        is_preconfigured=True,
    )
    db_session.add(feed)
    await db_session.commit()
    response = await client.delete(f"/api/v1/feeds/{feed.id}")
    assert response.status_code == 400
    events = await _events(db_session, "feed.delete")
    assert all(event.outcome != "succeeded" for event in events)
    assert [event.summary for event in events] == [
        {"reason": "preconfigured", "status": 400}
    ]


async def test_feed_trigger_audits_success_and_disabled_failure(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.core import database
    from cti.feeds import runner

    enabled = (
        await client.post(
            "/api/v1/feeds",
            json={"name": "Enabled", "feed_type": "file", "enabled": True},
        )
    ).json()
    disabled = (
        await client.post(
            "/api/v1/feeds",
            json={"name": "Disabled", "feed_type": "file", "enabled": False},
        )
    ).json()

    @asynccontextmanager
    async def test_session():
        yield db_session

    monkeypatch.setattr(database, "async_session_factory", test_session)
    monkeypatch.setattr(runner, "run_feed", AsyncMock())
    success = await client.post(f"/api/v1/feeds/{enabled['id']}/trigger")
    assert success.status_code == 200
    failed = await client.post(f"/api/v1/feeds/{disabled['id']}/trigger")
    assert failed.status_code == 400

    succeeded, rejected = await _events(db_session, "feed.trigger")
    assert (succeeded.resource_id, succeeded.resource_label, succeeded.outcome) == (
        enabled["id"],
        "Enabled",
        "succeeded",
    )
    assert uuid.UUID(succeeded.summary["run_id"])
    assert (rejected.resource_id, rejected.resource_label, rejected.outcome) == (
        disabled["id"],
        "Disabled",
        "failed",
    )
    assert rejected.summary == {"reason": "disabled", "status": 400}
