"""Audit events for the reports library (issue #16, task T4)."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cti.models.audit import AuditEvent
from cti.models.observable import Observable, ObservableType
from cti.models.report import Report, ReportOrigin
from cti.services import audit
from tests.policy_helpers import non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

REPORTS = "/api/v1/reports"
MISSING = "00000000-0000-0000-0000-000000000000"
BODY_SENTINEL = "BODY-SENTINEL-7f3a"
FILE_BYTES = b"FILE-SENTINEL-91c2 attachment text\n"


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


async def create(client: AsyncClient, **overrides: object) -> dict:
    payload = {
        "title": "APT notes",
        "origin": "internal",
        "summary": f"summary {BODY_SENTINEL}",
        "content": f"# Body {BODY_SENTINEL}",
        **overrides,
    }
    response = await client.post(REPORTS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class BrokenAuditSession:
    """An independent audit session whose commit always fails."""

    def add(self, _obj: object) -> None: ...

    async def commit(self) -> None:
        raise RuntimeError("audit table unavailable")

    async def __aenter__(self) -> BrokenAuditSession:
        return self

    async def __aexit__(self, *exc: object) -> None: ...


# ── create / update / delete ───────────────────────────────────────────────


async def test_create_records_event_without_body(client: AsyncClient, db_session) -> None:
    report = await create(client, tlp="amber")
    [event] = await events(db_session, "report.create")
    assert (event.outcome, event.resource_type, event.resource_id, event.resource_label) == (
        "succeeded",
        "report",
        report["id"],
        "APT notes",
    )
    assert (event.actor_type, event.actor_label) == ("api_key", "Test Key")
    assert event.summary == {"tlp": "amber"}
    assert BODY_SENTINEL not in await rows_json(db_session)


async def test_create_by_non_admin_is_denied(app: FastAPI, client: AsyncClient, db_session) -> None:
    async with non_admin_client(app) as user:
        response = await user.post(REPORTS, json={"title": "x", "origin": "internal"})
    assert response.status_code == 403
    found = await events(db_session, "report.create")
    assert_not_succeeded(found)
    assert [(e.outcome, e.actor_label, e.summary) for e in found] == [
        ("denied", "bob", {"reason": "not_admin", "status": 403})
    ]
    assert await db_session.scalar(select(Report.id)) is None


async def test_update_records_changed_field_names_and_tlp(client: AsyncClient, db_session) -> None:
    report = await create(client)
    response = await client.patch(
        f"{REPORTS}/{report['id']}",
        json={
            "title": "APT notes v2",
            "content": f"new {BODY_SENTINEL}",
            "origin": "internal",  # unchanged: not listed
            "tlp": "amber",
        },
    )
    assert response.status_code == 200, response.text
    [event] = await events(db_session, "report.update")
    assert event.outcome == "succeeded"
    assert event.resource_label == "APT notes v2"
    assert event.summary == {
        "changed_fields": ["content", "title", "tlp"],
        "tlp": {"before": None, "after": "amber"},
    }
    assert BODY_SENTINEL not in await rows_json(db_session)


async def test_update_without_tlp_change_has_no_tlp_entry(client: AsyncClient, db_session) -> None:
    report = await create(client, tlp="amber")
    response = await client.patch(f"{REPORTS}/{report['id']}", json={"tlp": "amber"})
    assert response.status_code == 200
    [event] = await events(db_session, "report.update")
    assert event.summary == {"changed_fields": []}


async def test_update_missing_report_records_failed(client: AsyncClient, db_session) -> None:
    response = await client.patch(f"{REPORTS}/{MISSING}", json={"title": "x"})
    assert response.status_code == 404
    found = await events(db_session, "report.update")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_id, e.summary) for e in found] == [
        ("failed", MISSING, {"reason": "not_found", "status": 404})
    ]


async def test_update_validation_failure_records_failed_and_changes_nothing(
    client: AsyncClient, db_session
) -> None:
    report = await create(client, tlp="amber")
    # Loosening a marking without tlp_change_reason is a service-level 422.
    response = await client.patch(f"{REPORTS}/{report['id']}", json={"tlp": "clear"})
    assert response.status_code == 422
    found = await events(db_session, "report.update")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_label, e.summary) for e in found] == [
        ("failed", "APT notes", {"reason": "invalid", "status": 422})
    ]
    assert await db_session.scalar(select(Report.tlp)) == "amber"


async def test_delete_keeps_earlier_history_with_label(client: AsyncClient, db_session) -> None:
    report = await create(client)
    await client.patch(f"{REPORTS}/{report['id']}", json={"summary": "edited"})
    response = await client.delete(f"{REPORTS}/{report['id']}")
    assert response.status_code == 204
    history = await events(db_session)
    assert [(e.action, e.outcome) for e in history] == [
        ("report.create", "succeeded"),
        ("report.update", "succeeded"),
        ("report.delete", "succeeded"),
    ]
    assert {e.resource_id for e in history} == {report["id"]}
    assert {e.resource_label for e in history} == {"APT notes"}
    assert await db_session.get(Report, uuid.UUID(report["id"])) is None


async def test_delete_missing_report_records_failed(client: AsyncClient, db_session) -> None:
    assert (await client.delete(f"{REPORTS}/{MISSING}")).status_code == 404
    found = await events(db_session, "report.delete")
    assert_not_succeeded(found)
    assert found[0].summary == {"reason": "not_found", "status": 404}


async def test_delete_by_non_admin_is_denied_with_resource_id(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    report = await create(client)
    async with non_admin_client(app) as user:
        assert (await user.delete(f"{REPORTS}/{report['id']}")).status_code == 403
    found = await events(db_session, "report.delete")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_id) for e in found] == [("denied", report["id"])]


# ── tags ───────────────────────────────────────────────────────────────────


async def test_tags_update_records_added_and_removed(client: AsyncClient, db_session) -> None:
    report = await create(client)
    url = f"{REPORTS}/{report['id']}/tags"
    assert (await client.put(url, json={"tags": ["apt", "phishing"]})).status_code == 200
    assert (await client.put(url, json={"tags": ["apt", "ransomware"]})).status_code == 200
    first, second = await events(db_session, "report.tags_update")
    assert first.summary == {"added": ["apt", "phishing"], "removed": []}
    assert second.summary == {"added": ["ransomware"], "removed": ["phishing"]}
    assert second.outcome == "succeeded"
    assert second.resource_label == "APT notes"


async def test_tags_update_missing_report_records_failed(client: AsyncClient, db_session) -> None:
    response = await client.put(f"{REPORTS}/{MISSING}/tags", json={"tags": ["apt"]})
    assert response.status_code == 404
    found = await events(db_session, "report.tags_update")
    assert_not_succeeded(found)
    assert found[0].outcome == "failed"


# ── attachments ────────────────────────────────────────────────────────────


async def upload(client: AsyncClient, report_id: str, name: str = "notes.txt"):
    return await client.put(
        f"{REPORTS}/{report_id}/attachment",
        files={"file": (name, FILE_BYTES, "text/plain")},
    )


async def test_attachment_upload_records_metadata_only(client: AsyncClient, db_session) -> None:
    report = await create(client)
    assert (await upload(client, report["id"])).status_code == 200
    [event] = await events(db_session, "report.attachment_upload")
    assert event.outcome == "succeeded"
    assert event.resource_label == "APT notes"
    assert event.summary == {
        "filename": "notes.txt",
        "media_type": "text/plain",
        "size_bytes": len(FILE_BYTES),
    }
    assert "FILE-SENTINEL" not in await rows_json(db_session)


async def test_attachment_upload_rejected_type_records_failed(
    client: AsyncClient, db_session
) -> None:
    report = await create(client)
    response = await upload(client, report["id"], name="payload.exe")
    assert response.status_code == 415
    found = await events(db_session, "report.attachment_upload")
    assert_not_succeeded(found)
    assert [(e.outcome, e.summary) for e in found] == [
        ("failed", {"reason": "unsupported_type", "status": 415})
    ]


async def test_attachment_delete_records_metadata(client: AsyncClient, db_session) -> None:
    report = await create(client)
    await upload(client, report["id"])
    assert (await client.delete(f"{REPORTS}/{report['id']}/attachment")).status_code == 204
    [event] = await events(db_session, "report.attachment_delete")
    assert event.outcome == "succeeded"
    assert event.summary == {
        "filename": "notes.txt",
        "media_type": "text/plain",
        "size_bytes": len(FILE_BYTES),
    }


async def test_attachment_delete_without_attachment_records_failed(
    client: AsyncClient, db_session
) -> None:
    report = await create(client)
    assert (await client.delete(f"{REPORTS}/{report['id']}/attachment")).status_code == 404
    found = await events(db_session, "report.attachment_delete")
    assert_not_succeeded(found)
    assert found[0].summary == {"reason": "not_found", "status": 404}


async def test_attachment_download_records_initiated_and_completed(
    client: AsyncClient, db_session
) -> None:
    report = await create(client, tlp="amber")
    await upload(client, report["id"], name="notes v1.txt")
    response = await client.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 200
    assert response.content == FILE_BYTES
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''notes%20v1.txt"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-tlp-marking"] == "amber"

    initiated, completed = await events(db_session, "report.attachment_download")
    assert (initiated.outcome, completed.outcome) == ("initiated", "completed")
    assert initiated.resource_id == completed.resource_id == report["id"]
    assert initiated.resource_label == "APT notes"
    assert initiated.summary == {
        "filename": "notes v1.txt",
        "media_type": "text/plain",
        "size_bytes": len(FILE_BYTES),
        "tlp": "amber",
    }
    assert completed.summary == {
        "bytes_sent": len(FILE_BYTES),
        "initiated_event_id": str(initiated.id),
    }
    assert "FILE-SENTINEL" not in await rows_json(db_session)


async def test_attachment_download_refused_when_initiated_write_fails(
    client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = await create(client)
    await upload(client, report["id"])
    monkeypatch.setattr(audit, "_session_factory", BrokenAuditSession)
    response = await client.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 503
    assert response.json() == {"detail": "Audit log unavailable"}
    assert b"FILE-SENTINEL" not in response.content
    assert await events(db_session, "report.attachment_download") == []


async def test_attachment_download_missing_records_failed_without_disclosure(
    client: AsyncClient, db_session
) -> None:
    report = await create(client)  # no attachment
    response = await client.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 404
    found = await events(db_session, "report.attachment_download")
    assert [(e.outcome, e.summary) for e in found] == [
        ("failed", {"reason": "not_found", "status": 404})
    ]


async def test_attachment_download_of_red_report_by_api_key_leaks_nothing(
    client: AsyncClient, db_session
) -> None:
    report = Report(title="Named recipients", origin=ReportOrigin.INTERNAL, tlp="red")
    db_session.add(report)
    await db_session.commit()
    report_id = str(report.id)
    response = await client.get(f"{REPORTS}/{report_id}/attachment")
    assert response.status_code == 404
    found = await events(db_session, "report.attachment_download")
    assert [(e.outcome, e.resource_id, e.resource_label) for e in found] == [
        ("failed", report_id, None)
    ]
    assert "Named recipients" not in await rows_json(db_session)


# ── observables and import ─────────────────────────────────────────────────


async def add_observable(db: AsyncSession, value: str = "linked.example") -> str:
    observable = Observable(type=ObservableType.DOMAIN_NAME, value=value, confidence_score=80)
    db.add(observable)
    await db.commit()
    return str(observable.id)


async def test_link_and_unlink_record_observable_ids(client: AsyncClient, db_session) -> None:
    report = await create(client)
    observable_id = await add_observable(db_session)
    url = f"{REPORTS}/{report['id']}/observables"
    assert (await client.post(url, json={"observable_id": observable_id})).status_code == 201
    assert (await client.delete(f"{url}/{observable_id}")).status_code == 204
    [link] = await events(db_session, "report.observable_link")
    [unlink] = await events(db_session, "report.observable_unlink")
    assert (link.outcome, link.summary) == (
        "succeeded",
        {"observable_id": observable_id, "created": True},
    )
    assert (unlink.outcome, unlink.summary) == ("succeeded", {"observable_id": observable_id})
    assert link.resource_label == unlink.resource_label == "APT notes"
    assert "linked.example" not in await rows_json(db_session)


async def test_link_missing_observable_records_failed(client: AsyncClient, db_session) -> None:
    report = await create(client)
    url = f"{REPORTS}/{report['id']}/observables"
    assert (await client.post(url, json={"observable_id": MISSING})).status_code == 404
    found = await events(db_session, "report.observable_link")
    assert_not_succeeded(found)
    assert found[0].summary == {"observable_id": MISSING, "reason": "not_found", "status": 404}


async def test_unlink_missing_link_records_failed(client: AsyncClient, db_session) -> None:
    report = await create(client)
    observable_id = await add_observable(db_session)
    url = f"{REPORTS}/{report['id']}/observables/{observable_id}"
    assert (await client.delete(url)).status_code == 404
    found = await events(db_session, "report.observable_unlink")
    assert_not_succeeded(found)
    assert found[0].summary["reason"] == "not_found"


async def test_import_records_counts_and_ids_not_values(client: AsyncClient, db_session) -> None:
    report = await create(client, content="Seen evil-import.example and 185.220.101.42 today.")
    body = {
        "confidence": 60,
        "items": [
            {"type": "domain-name", "value": "evil-import.example"},
            {"type": "ip-addr", "value": "185.220.101.42"},
        ],
    }
    response = await client.post(f"{REPORTS}/{report['id']}/import", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    [event] = await events(db_session, "report.import")
    assert event.outcome == "succeeded"
    assert event.summary == {
        "requested": 2,
        "created": result["created"],
        "attributed_existing": result["attributed_existing"],
        "already_attributed": result["already_attributed"],
        "skipped": 0,
        "observable_ids": [item["id"] for item in result["observables"]],
    }
    assert result["created"] == 2
    dumped = await rows_json(db_session)
    assert "evil-import.example" not in dumped
    assert "185.220.101.42" not in dumped


async def test_import_non_candidate_records_failed(client: AsyncClient, db_session) -> None:
    report = await create(client, content="nothing to see")
    body = {"confidence": 60, "items": [{"type": "domain-name", "value": "absent.example"}]}
    response = await client.post(f"{REPORTS}/{report['id']}/import", json=body)
    assert response.status_code == 422
    found = await events(db_session, "report.import")
    assert_not_succeeded(found)
    assert [(e.outcome, e.summary) for e in found] == [
        ("failed", {"requested": 1, "reason": "invalid", "status": 422})
    ]
    assert "absent.example" not in await rows_json(db_session)


async def test_failing_audit_insert_rolls_back_report_create(
    client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = audit._build_event

    def unstorable(**kwargs: object) -> AuditEvent:
        event = build(**kwargs)
        event.action = None  # violates NOT NULL, so the shared commit fails
        return event

    monkeypatch.setattr(audit, "_build_event", unstorable)
    with pytest.raises(IntegrityError):
        await client.post(REPORTS, json={"title": "Never stored", "origin": "internal"})
    await db_session.rollback()
    assert await db_session.scalar(select(Report.id)) is None
    assert await events(db_session) == []
