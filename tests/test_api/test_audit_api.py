"""Audit history API, plus the core helpers exercised through real requests."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.api_key import ApiKey
from cti.models.audit import AuditEvent
from cti.models.observable import ObservableType
from cti.models.user import UserRole
from cti.services import audit
from cti.services.audit import Actor, ActorType, AuditOutcome
from tests.policy_helpers import non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

URL = "/api/v1/audit/events"
T0 = datetime(2026, 11, 2, 10, tzinfo=UTC)
ALICE = Actor(ActorType.USER, "11111111-1111-1111-1111-111111111111", "alice")
KEY = Actor(ActorType.API_KEY, "22222222-2222-2222-2222-222222222222", "Firewall")
JOB = audit.system_actor("system:audit_retention", "Audit retention")


async def seed(db: AsyncSession) -> list[AuditEvent]:
    """Six events, one minute apart, oldest first."""
    specs = [
        (ALICE, "report.create", "r1", AuditOutcome.SUCCEEDED),
        (ALICE, "report.update", "r1", AuditOutcome.SUCCEEDED),
        (KEY, "export.download", "json", AuditOutcome.INITIATED),
        (KEY, "export.download", "json", AuditOutcome.COMPLETED),
        (ALICE, "feed.delete", "f1", AuditOutcome.DENIED),
        (JOB, "audit.retention_cleanup", None, AuditOutcome.SUCCEEDED),
    ]
    events = []
    for i, (actor, action, resource_id, outcome) in enumerate(specs):
        event = audit.record(
            db,
            actor=actor,
            action=action,
            resource_type=audit.ACTION_CATALOG[action],
            resource_id=resource_id,
            outcome=outcome,
            summary={"n": i},
        )
        event.occurred_at = T0 + timedelta(minutes=i)
        events.append(event)
    await db.commit()
    return events


@pytest.fixture
async def admin(app: FastAPI):
    """Interactive admin-user client: the only caller allowed to read history."""
    async with non_admin_client(app, role=UserRole.admin) as ac:
        yield ac


async def test_api_keys_cannot_read_history(client: AsyncClient, db_session) -> None:
    await seed(db_session)
    for url in (URL, "/api/v1/audit/meta"):
        response = await client.get(url)
        assert response.status_code == 403
        assert "interactive admin" in response.json()["detail"]


def summaries(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["summary"]["n"] for item in response.json()["items"]]


# ── listing ────────────────────────────────────────────────────────────────


async def test_list_shape_and_newest_first(admin: AsyncClient, db_session) -> None:
    events = await seed(db_session)
    response = await admin.get(URL)
    body = response.json()
    assert (body["total"], body["page"], body["size"], body["pages"]) == (6, 1, 50, 1)
    assert summaries(response) == [5, 4, 3, 2, 1, 0]
    first = body["items"][-1]
    assert first == {
        "id": str(events[0].id),
        "occurred_at": "2026-11-02T10:00:00Z",
        "actor_type": "user",
        "actor_id": ALICE.id,
        "actor_label": "alice",
        "action": "report.create",
        "resource_type": "report",
        "resource_id": "r1",
        "resource_label": None,
        "outcome": "succeeded",
        "summary": {"n": 0},
    }


async def test_ties_ordered_by_id_desc(admin: AsyncClient, db_session) -> None:
    events = await seed(db_session)
    for event in events:
        event.occurred_at = T0
    await db_session.commit()
    ids = [item["id"] for item in (await admin.get(URL)).json()["items"]]
    assert ids == sorted(ids, reverse=True)


async def test_pagination(admin: AsyncClient, db_session) -> None:
    await seed(db_session)
    page1 = await admin.get(URL, params={"size": 4})
    page2 = await admin.get(URL, params={"size": 4, "page": 2})
    page3 = await admin.get(URL, params={"size": 4, "page": 3})
    assert summaries(page1) == [5, 4, 3, 2]
    assert summaries(page2) == [1, 0]
    assert summaries(page3) == []
    assert page2.json()["pages"] == 2 and page2.json()["total"] == 6
    empty = (await admin.get(URL, params={"action": "tag.create"})).json()
    assert (empty["total"], empty["pages"], empty["items"]) == (0, 0, [])


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"size": 0},
        {"size": 101},
        {"outcome": "ok"},
        {"actor_type": "robot"},
        {"since": "yesterday"},
        {"actor_id": "x" * 65},
    ],
)
async def test_invalid_params_rejected(admin: AsyncClient, params: dict) -> None:
    assert (await admin.get(URL, params=params)).status_code == 422


async def test_size_upper_bound_accepted(admin: AsyncClient, db_session) -> None:
    await seed(db_session)
    assert len(summaries(await admin.get(URL, params={"size": 100}))) == 6


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"since": "2026-11-02T10:02:00Z"}, [5, 4, 3, 2]),  # inclusive
        ({"until": "2026-11-02T10:02:00Z"}, [1, 0]),  # exclusive
        ({"since": "2026-11-02T10:01:00Z", "until": "2026-11-02T10:03:00Z"}, [2, 1]),
        # Offsets are normalized to UTC: 12:02+02:00 is 10:02Z.
        ({"since": "2026-11-02T12:02:00+02:00"}, [5, 4, 3, 2]),
        ({"actor_type": "api_key"}, [3, 2]),
        ({"actor_type": "system"}, [5]),
        ({"actor_id": ALICE.id}, [4, 1, 0]),
        ({"actor_type": "user", "actor_id": KEY.id}, []),
        ({"action": "report.create"}, [0]),
        ({"action": ["report.create", "feed.delete"]}, [4, 0]),
        ({"action": "report"}, []),  # exact match only
        ({"resource_type": "report"}, [1, 0]),
        ({"resource_type": "report", "resource_id": "r1"}, [1, 0]),
        ({"resource_id": "json"}, [3, 2]),
        ({"outcome": "denied"}, [4]),
        ({"outcome": ["initiated", "completed"]}, [3, 2]),
        ({"action": "export.download", "outcome": "completed", "actor_type": "api_key"}, [3]),
    ],
)
async def test_filters(admin: AsyncClient, db_session, params: dict, expected: list[int]) -> None:
    await seed(db_session)
    response = await admin.get(URL, params=params)
    assert summaries(response) == expected
    assert response.json()["total"] == len(expected)


# ── authorization and immutability ─────────────────────────────────────────


async def test_requires_authentication(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        assert (await anon.get(URL)).status_code == 401
        assert (await anon.get("/api/v1/audit/meta")).status_code == 401


async def test_non_admin_user_gets_403(app: FastAPI, db_session) -> None:
    await seed(db_session)
    async with non_admin_client(app) as user:
        assert (await user.get(URL)).status_code == 403
        assert (await user.get("/api/v1/audit/meta")).status_code == 403
    async with non_admin_client(app, role=UserRole.admin) as admin:
        assert (await admin.get(URL)).json()["total"] == 6


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_no_mutation_routes(admin: AsyncClient, db_session, method: str) -> None:
    [event, *_] = await seed(db_session)
    assert (await admin.request(method, URL, json={})).status_code == 405
    item = await admin.request(method, f"{URL}/{event.id}", json={})
    assert item.status_code in (404, 405)
    assert (await admin.request(method, "/api/v1/audit/meta", json={})).status_code == 405
    assert len((await db_session.scalars(select(AuditEvent))).all()) == 6


async def test_meta_exposes_catalog(admin: AsyncClient) -> None:
    body = (await admin.get("/api/v1/audit/meta")).json()
    assert body["actions"] == list(audit.ACTION_CATALOG)
    assert {"report.attachment_download", "ai.request", "audit.retention_cleanup"} <= set(
        body["actions"]
    )
    assert body["actor_types"] == ["user", "api_key", "system"]
    assert body["outcomes"] == [
        "succeeded",
        "failed",
        "denied",
        "initiated",
        "completed",
        "interrupted",
    ]
    assert body["resource_types"] == sorted(set(audit.ACTION_CATALOG.values()))
    assert body["retention_days"] == 365


# ── helpers through real requests ──────────────────────────────────────────

test_router = APIRouter()
DOWNLOAD_BODY = b"203.0.113.7\n" * 500


@test_router.post("/allowlist")
async def _create_allowlisted(
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
) -> dict:
    entry = AllowlistEntry(
        kind=AllowlistKind.EXACT,
        value="198.51.100.1",
        observable_type=ObservableType.IP_ADDR,
        reason="known good",
    )
    db.add(entry)
    await db.flush()
    audit.record(
        db,
        actor=audit.actor_from_auth(auth),
        action="allowlist.create",
        resource_type="allowlist_entry",
        resource_id=entry.id,
        resource_label=entry.value,
        summary={"kind": "exact", "reason_length": len(entry.reason)},
    )
    await db.commit()
    return {"id": str(entry.id)}


@test_router.get("/download")
async def _download(auth: AuthSubject = Depends(get_current_auth)) -> audit.AuditedDownload:
    disclosure = await audit.begin_disclosure(
        actor=audit.actor_from_auth(auth),
        action="export.download",
        resource_type="export",
        resource_id="text",
    )
    return audit.AuditedDownload(
        DOWNLOAD_BODY, disclosure=disclosure, media_type="text/plain", chunk_size=1000
    )


@test_router.delete("/guarded/{entry_id}", status_code=204)
async def _guarded(
    entry_id: uuid.UUID,
    _auth: AuthSubject = Depends(
        audit.audited_admin("allowlist.delete", "allowlist_entry", resource_id_param="entry_id")
    ),
) -> None:
    return None


@pytest.fixture
def helper_app(app: FastAPI) -> FastAPI:
    app.include_router(test_router, prefix="/test-audit")
    return app


async def stored(db: AsyncSession) -> list[AuditEvent]:
    db.expunge_all()
    rows = await db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at))
    return list(rows.all())


async def test_api_key_attribution_uses_record_id_not_raw_key(
    client: AsyncClient, helper_app: FastAPI, db_session, seeded_api_key: str
) -> None:
    response = await client.post("/test-audit/allowlist")
    assert response.status_code == 200
    key = (await db_session.scalars(select(ApiKey))).one()
    [event] = await stored(db_session)
    assert (event.actor_type, event.actor_id, event.actor_label) == (
        "api_key",
        str(key.id),
        "Test Key",
    )
    assert event.resource_id == response.json()["id"]
    row = (await db_session.execute(select(AuditEvent.__table__))).one()
    dumped = json.dumps(list(row), default=str)
    assert seeded_api_key not in dumped
    assert key.key_hash not in dumped
    assert seeded_api_key[:12] not in dumped  # not even the display prefix

    # API keys cannot read the history at all; admins see the record id only.
    assert (await client.get(URL)).status_code == 403
    async with non_admin_client(helper_app, role=UserRole.admin) as admin:
        listed = (await admin.get(URL)).json()["items"]
    assert listed[0]["actor_id"] == str(key.id)
    assert seeded_api_key not in json.dumps(listed)


async def test_download_records_initiated_and_completed(
    client: AsyncClient, helper_app: FastAPI, db_session
) -> None:
    response = await client.get("/test-audit/download")
    assert response.status_code == 200
    assert response.content == DOWNLOAD_BODY
    initiated, completed = await stored(db_session)
    assert (initiated.outcome, completed.outcome) == ("initiated", "completed")
    assert completed.summary == {
        "bytes_sent": len(DOWNLOAD_BODY),
        "initiated_event_id": str(initiated.id),
    }
    assert initiated.actor_type == completed.actor_type == "api_key"


async def test_download_refused_when_initiated_write_fails(
    client: AsyncClient, helper_app: FastAPI, db_session, monkeypatch
) -> None:
    class Broken:
        def add(self, _obj: object) -> None: ...

        async def commit(self) -> None:
            raise RuntimeError("audit table unavailable")

        async def __aenter__(self) -> Broken:
            return self

        async def __aexit__(self, *exc: object) -> None: ...

    monkeypatch.setattr(audit, "_session_factory", Broken)
    response = await client.get("/test-audit/download")
    assert response.status_code == 503
    assert response.json() == {"detail": "Audit log unavailable"}
    assert b"203.0.113.7" not in response.content
    assert await stored(db_session) == []


async def test_audited_admin_records_denied_then_403(
    client: AsyncClient, helper_app: FastAPI, db_session
) -> None:
    target = uuid.uuid4()
    async with non_admin_client(helper_app) as user:
        response = await user.delete(f"/test-audit/guarded/{target}")
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}
    [event] = await stored(db_session)
    assert (event.action, event.outcome, event.actor_type, event.actor_label) == (
        "allowlist.delete",
        "denied",
        "user",
        "bob",
    )
    assert event.resource_id == str(target)
    assert event.summary == {"reason": "not_admin", "status": 403}

    # Admins and API keys pass without any event; unauthenticated is 401, unaudited.
    assert (await client.delete(f"/test-audit/guarded/{target}")).status_code == 204
    async with non_admin_client(helper_app, role=UserRole.admin) as admin:
        assert (await admin.delete(f"/test-audit/guarded/{target}")).status_code == 204
    transport = ASGITransport(app=helper_app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.delete(f"/test-audit/guarded/{target}")).status_code == 401
    assert len(await stored(db_session)) == 1


async def test_audited_admin_denied_is_never_succeeded(helper_app: FastAPI, db_session) -> None:
    async with non_admin_client(helper_app) as user:
        for _ in range(3):
            await user.delete(f"/test-audit/guarded/{uuid.uuid4()}")
    assert {e.outcome for e in await stored(db_session)} == {"denied"}


def test_audited_admin_rejects_unknown_action() -> None:
    with pytest.raises(ValueError):
        audit.audited_admin("allowlist.delete", "report")
