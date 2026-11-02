"""Audit coverage for allowlist, export profiles, and export disclosures."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from cti.models.allowlist import AllowlistEntry
from cti.models.api_key import ApiKey
from cti.models.audit import AuditEvent
from cti.services import audit
from tests.policy_helpers import add_observable


async def _events(db, action: str) -> list[AuditEvent]:
    db.expunge_all()
    rows = await db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == action)
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    )
    return list(rows.all())


async def test_allowlist_create_delete_audits_success_failure_and_api_key_attribution(
    client: AsyncClient, db_session, seeded_api_key: str
) -> None:
    body = {
        "kind": "exact",
        "value": "198.51.100.9",
        "observable_type": "ip-addr",
        "reason": "approved false positive",
    }
    created = await client.post("/api/v1/allowlist", json=body)
    assert created.status_code == 201
    entry_id = created.json()["id"]
    assert (await client.post("/api/v1/allowlist", json=body)).status_code == 409
    assert (await client.delete(f"/api/v1/allowlist/{entry_id}")).status_code == 204
    assert (await client.delete(f"/api/v1/allowlist/{entry_id}")).status_code == 404

    key = (await db_session.scalars(select(ApiKey))).one()
    create_ok, create_failed = await _events(db_session, "allowlist.create")
    delete_ok, delete_failed = await _events(db_session, "allowlist.delete")
    assert (create_ok.actor_type, create_ok.actor_id, create_ok.actor_label) == (
        "api_key",
        str(key.id),
        "Test Key",
    )
    assert (create_ok.resource_id, create_ok.resource_label, create_ok.outcome) == (
        entry_id,
        "198.51.100.9",
        "succeeded",
    )
    assert create_ok.summary == {
        "kind": "exact",
        "observable_type": "ip-addr",
        "reason_length": len(body["reason"]),
    }
    assert (create_failed.outcome, create_failed.summary["reason"]) == ("failed", "duplicate")
    assert (delete_ok.outcome, delete_ok.resource_id) == ("succeeded", entry_id)
    assert (delete_failed.outcome, delete_failed.summary["reason"]) == (
        "failed",
        "not_found",
    )
    dumped = json.dumps(
        [
            list(row)
            for row in (await db_session.execute(select(AuditEvent.__table__))).all()
        ],
        default=str,
    )
    assert seeded_api_key not in dumped
    assert key.key_hash not in dumped


async def test_export_profile_create_update_delete_audits_success_and_failure(
    client: AsyncClient, db_session
) -> None:
    create_body = {"name": "Audit profile", "format": "text", "confidence_min": 0}
    created = await client.post("/api/v1/export/profiles", json=create_body)
    assert created.status_code == 201
    profile_id = created.json()["id"]
    assert (await client.post("/api/v1/export/profiles", json=create_body)).status_code == 409
    updated = await client.put(
        f"/api/v1/export/profiles/{profile_id}", json={"name": "Renamed", "max_age_days": 7}
    )
    assert updated.status_code == 200
    missing = uuid.uuid4()
    assert (
        await client.put(f"/api/v1/export/profiles/{missing}", json={"name": "nope"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/export/profiles/{profile_id}")).status_code == 204
    assert (await client.delete(f"/api/v1/export/profiles/{profile_id}")).status_code == 404

    create_ok, create_failed = await _events(db_session, "export_profile.create")
    update_ok, update_failed = await _events(db_session, "export_profile.update")
    delete_ok, delete_failed = await _events(db_session, "export_profile.delete")
    assert (create_ok.resource_id, create_ok.resource_label, create_ok.outcome) == (
        profile_id,
        "Audit profile",
        "succeeded",
    )
    assert create_ok.summary == {"changed_fields": ["confidence_min", "format", "name"]}
    assert create_failed.summary == {"reason": "duplicate_name", "status": 409}
    assert (update_ok.resource_label, update_ok.summary) == (
        "Renamed",
        {"changed_fields": ["max_age_days", "name"]},
    )
    assert (update_failed.resource_id, update_failed.outcome) == (str(missing), "failed")
    assert (delete_ok.resource_id, delete_ok.resource_label) == (profile_id, "Renamed")
    assert (delete_failed.outcome, delete_failed.summary["reason"]) == (
        "failed",
        "not_found",
    )


@pytest.mark.parametrize(
    ("url", "resource_id", "expected_format"),
    [
        ("/api/v1/export/json", "json", "json"),
        ("/api/v1/export/text", "text", "text"),
        ("/api/v1/export/blocklist/ip-addr", "blocklist:ip-addr", "blocklist"),
    ],
)
async def test_ad_hoc_downloads_record_initiated_and_completed(
    client: AsyncClient, db_session, url: str, resource_id: str, expected_format: str
) -> None:
    await add_observable(db_session, "203.0.113.17")
    response = await client.get(url)
    assert response.status_code == 200
    initiated, completed = await _events(db_session, "export.download")
    assert (initiated.resource_id, initiated.outcome) == (resource_id, "initiated")
    assert initiated.summary == {"format": expected_format, "count": 1, "tlp_excluded": 0}
    assert completed.outcome == "completed"
    assert completed.summary["initiated_event_id"] == str(initiated.id)
    assert completed.summary["bytes_sent"] == len(response.content)


async def test_profile_download_and_cache_hit_are_audited(
    client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.api.v1 import export as export_api

    cached: dict[str, str] = {}

    async def cache_get(key: str) -> str | None:
        return cached.get(key)

    async def cache_set(key: str, value: str, ttl_seconds: int) -> None:
        assert ttl_seconds == 300
        cached[key] = value

    monkeypatch.setattr(export_api, "cache_get", cache_get)
    monkeypatch.setattr(export_api, "cache_set", cache_set)
    await add_observable(db_session, "203.0.113.18")
    profile = (
        await client.post(
            "/api/v1/export/profiles",
            json={"name": "Profile", "format": "text", "confidence_min": 0},
        )
    ).json()
    response = await client.get(f"/api/v1/export/profiles/{profile['id']}/download")
    assert response.status_code == 200
    await client.get("/api/v1/export/blocklist/ip-addr")
    hit = await client.get("/api/v1/export/blocklist/ip-addr")
    assert hit.headers["X-Cache"] == "HIT"

    downloads = await _events(db_session, "export.download")
    initiated = [event for event in downloads if event.outcome == "initiated"]
    completed = [event for event in downloads if event.outcome == "completed"]
    assert len(initiated) == len(completed) == 3
    profile_event = initiated[0]
    assert (profile_event.resource_id, profile_event.resource_label) == (
        profile["id"],
        "Profile",
    )
    assert profile_event.summary == {"format": "text", "count": 1, "tlp_excluded": 0}
    assert [event.resource_id for event in initiated[1:]] == [
        "blocklist:ip-addr",
        "blocklist:ip-addr",
    ]


async def test_profile_download_not_found_records_failed(client: AsyncClient, db_session) -> None:
    missing = uuid.uuid4()
    response = await client.get(f"/api/v1/export/profiles/{missing}/download")
    assert response.status_code == 404
    [event] = await _events(db_session, "export.download")
    assert (event.resource_id, event.outcome, event.summary) == (
        str(missing),
        "failed",
        {"reason": "not_found", "status": 404},
    )


async def test_download_audit_write_failure_returns_503_without_export_content(
    client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_observable(db_session, "203.0.113.199")

    class Broken:
        def add(self, _obj: object) -> None: ...

        async def commit(self) -> None:
            raise RuntimeError("audit unavailable")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None: ...

    monkeypatch.setattr(audit, "_session_factory", Broken)
    response = await client.get("/api/v1/export/text")
    assert response.status_code == 503
    assert response.json() == {"detail": "Audit log unavailable"}
    assert b"203.0.113.199" not in response.content
    assert await _events(db_session, "export.download") == []


async def test_failed_commit_rolls_back_allowlist_success_event(
    app, db_session, seeded_api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_commit = db_session.commit
    monkeypatch.setattr(db_session, "commit", AsyncMock(side_effect=RuntimeError("commit failed")))
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as failing:
        failing.headers["X-API-Key"] = seeded_api_key
        response = await failing.post(
            "/api/v1/allowlist",
            json={
                "kind": "exact",
                "value": "192.0.2.200",
                "observable_type": "ip-addr",
                "reason": "test rollback",
            },
        )
    assert response.status_code == 500
    monkeypatch.setattr(db_session, "commit", real_commit)
    await db_session.rollback()
    assert (await db_session.scalars(select(AllowlistEntry))).all() == []
    assert await _events(db_session, "allowlist.create") == []
