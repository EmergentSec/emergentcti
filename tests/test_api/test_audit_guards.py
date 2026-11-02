"""Covered admin mutations record real-route non-admin denials."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from cti.models.audit import AuditEvent
from tests.policy_helpers import non_admin_client


@pytest.mark.parametrize(
    ("method", "path", "body", "action", "resource_id"),
    [
        (
            "post",
            "/api/v1/allowlist",
            {"kind": "cidr", "value": "10.0.0.0/8", "reason": "r"},
            "allowlist.create",
            None,
        ),
        ("delete", "/api/v1/allowlist/{id}", None, "allowlist.delete", "path"),
        (
            "post",
            "/api/v1/export/profiles",
            {"name": "Denied", "format": "text"},
            "export_profile.create",
            None,
        ),
        (
            "put",
            "/api/v1/export/profiles/{id}",
            {"name": "Denied"},
            "export_profile.update",
            "path",
        ),
        (
            "delete",
            "/api/v1/export/profiles/{id}",
            None,
            "export_profile.delete",
            "path",
        ),
        (
            "post",
            "/api/v1/feeds",
            {"name": "Denied", "feed_type": "file"},
            "feed.create",
            None,
        ),
        ("put", "/api/v1/feeds/{id}", {"enabled": False}, "feed.update", "path"),
        ("delete", "/api/v1/feeds/{id}", None, "feed.delete", "path"),
        ("post", "/api/v1/feeds/{id}/trigger", None, "feed.trigger", "path"),
        ("post", "/api/v1/tags", {"name": "denied"}, "tag.create", None),
        ("delete", "/api/v1/tags/{id}", None, "tag.delete", "path"),
        (
            "put",
            "/api/v1/observables/{id}/tlp-override",
            {"tlp": "green", "reason": "denied"},
            "observable.tlp_override_set",
            "path",
        ),
        (
            "delete",
            "/api/v1/observables/{id}/tlp-override",
            None,
            "observable.tlp_override_clear",
            "path",
        ),
        (
            "put",
            "/api/v1/observables/{id}/tags",
            {"tags": ["denied"]},
            "observable.tags_update",
            "path",
        ),
    ],
)
async def test_non_admin_mutation_records_denied_event(
    app, db_session, method: str, path: str, body: dict | None, action: str, resource_id: str | None
) -> None:
    target_id = uuid.uuid4()
    path = path.format(id=target_id)
    async with non_admin_client(app) as user:
        response = await user.request(method, path, json=body)
    assert response.status_code == 403

    [event] = list(
        (
            await db_session.scalars(select(AuditEvent).where(AuditEvent.action == action))
        ).all()
    )
    assert (event.actor_type, event.actor_label, event.outcome) == ("user", "bob", "denied")
    assert event.actor_id is not None
    assert event.resource_id == (str(target_id) if resource_id == "path" else None)
    assert event.summary == {"reason": "not_admin", "status": 403}
    assert not list(
        (
            await db_session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == action, AuditEvent.outcome == "succeeded"
                )
            )
        ).all()
    )
