"""Reports library API contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select

from cti.core.config import get_settings
from cti.core.dependencies import get_current_auth
from cti.models.observable import Observable, ObservableType
from cti.models.report import Report, ReportAttachment, report_observables
from cti.models.user import User, UserRole
from cti.services import report_service, retention

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

REPORTS = "/api/v1/reports"
MISSING_ID = "00000000-0000-0000-0000-000000000000"


async def create_report(client: AsyncClient, **overrides: object) -> dict:
    payload = {
        "title": "Provider bulletin",
        "origin": "provider",
        "source_name": "Provider One",
        "summary": "Threat activity summary",
        "content": "# Findings",
        **overrides,
    }
    response = await client.post(REPORTS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def analyst(db_session: AsyncSession) -> User:
    user = User(
        username="reports-analyst",
        password_hash="unused",
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def analyst_client(
    app: FastAPI,
    analyst: User,
) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate_as_analyst() -> User:
        return analyst

    app.dependency_overrides[get_current_auth] = authenticate_as_analyst
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


@pytest.fixture
async def anonymous_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_admin_crud_and_untrusted_markdown_round_trip(client: AsyncClient) -> None:
    unsafe = "# Heading\n<script>alert('render elsewhere')</script>"
    created = await create_report(
        client,
        title="  Internal analysis  ",
        origin="internal",
        source_name="SOC",
        content=unsafe,
        content_format="markdown",
        source_url="https://example.test/source",
    )
    assert created["title"] == "Internal analysis"
    assert created["content"] == unsafe
    assert created["has_attachment"] is False
    assert created["observables"] == []

    response = await client.patch(
        f"{REPORTS}/{created['id']}",
        json={"summary": "Updated", "content_format": "text"},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "Updated"
    assert response.json()["content_format"] == "text"

    response = await client.get(f"{REPORTS}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["content"] == unsafe

    response = await client.delete(f"{REPORTS}/{created['id']}")
    assert response.status_code == 204
    assert (await client.get(f"{REPORTS}/{created['id']}")).status_code == 404


async def test_ai_provenance_round_trip_and_unknown_values(client: AsyncClient) -> None:
    generated_at = "2026-10-31T15:30:00"
    known = await create_report(
        client,
        title="AI report",
        origin="internal",
        is_ai_generated=True,
        ai_provider="OpenAI",
        ai_model="model-x",
        ai_generated_at=generated_at,
    )
    assert known["is_ai_generated"] is True
    assert known["ai_provider"] == "OpenAI"
    assert known["ai_model"] == "model-x"
    assert known["ai_generated_at"] == generated_at

    unknown = await create_report(
        client,
        title="Historical AI report",
        origin="internal",
        is_ai_generated=True,
        ai_provider=None,
        ai_model=None,
        ai_generated_at=None,
    )
    assert unknown["ai_provider"] is None
    assert unknown["ai_model"] is None
    assert unknown["ai_generated_at"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ai_provider", "x"),
        ("ai_model", "x"),
        ("ai_generated_at", "2026-01-01T00:00:00"),
    ],
)
async def test_ai_fields_rejected_for_non_ai_reports(
    client: AsyncClient,
    field: str,
    value: str,
) -> None:
    response = await client.post(
        REPORTS,
        json={"title": "Human", "origin": "internal", field: value},
    )
    assert response.status_code == 422

    report = await create_report(client, title=f"Patch {field}", origin="internal")
    response = await client.patch(f"{REPORTS}/{report['id']}", json={field: value})
    assert response.status_code == 422


async def test_disabling_ai_requires_clearing_provenance(client: AsyncClient) -> None:
    report = await create_report(
        client,
        title="Generated",
        origin="internal",
        is_ai_generated=True,
        ai_model="old-model",
    )
    response = await client.patch(
        f"{REPORTS}/{report['id']}",
        json={"is_ai_generated": False},
    )
    assert response.status_code == 422

    response = await client.patch(
        f"{REPORTS}/{report['id']}",
        json={"is_ai_generated": False, "ai_model": None},
    )
    assert response.status_code == 200
    assert response.json()["is_ai_generated"] is False


@pytest.mark.parametrize("field", ["title", "origin", "content_format", "is_ai_generated"])
async def test_nonnullable_fields_reject_null_on_update(
    client: AsyncClient,
    field: str,
) -> None:
    report = await create_report(client, title=f"Null {field}")
    response = await client.patch(f"{REPORTS}/{report['id']}", json={field: None})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "source_url",
    ["ftp://example.test/report", "javascript:alert(1)", "example.test/report"],
)
async def test_non_http_source_url_rejected(client: AsyncClient, source_url: str) -> None:
    response = await client.post(
        REPORTS,
        json={"title": "Bad URL", "origin": "provider", "source_url": source_url},
    )
    assert response.status_code == 422


async def test_search_treats_like_wildcards_literally(client: AsyncClient) -> None:
    await create_report(client, title="100% confirmed")
    await create_report(client, title="1000 confirmed")
    await create_report(client, title="file_name report")
    await create_report(client, title="filename report")

    response = await client.get(REPORTS, params={"q": "100%"})
    assert [item["title"] for item in response.json()["items"]] == ["100% confirmed"]
    response = await client.get(REPORTS, params={"q": "file_name"})
    assert [item["title"] for item in response.json()["items"]] == ["file_name report"]


async def test_search_filters_sources_and_pagination(client: AsyncClient) -> None:
    await create_report(
        client,
        title="Alpha campaign",
        source_name="Vendor A",
        summary="needle",
        published_at="2026-01-15T10:00:00",
    )
    await create_report(
        client,
        title="Beta campaign",
        source_name="Vendor B",
        published_at="2026-02-15T10:00:00",
        is_ai_generated=True,
    )
    await create_report(
        client,
        title="Internal needle",
        origin="internal",
        source_name="SOC",
        published_at="2026-03-15T10:00:00",
    )

    response = await client.get(REPORTS, params={"q": "NEEDLE"})
    assert response.status_code == 200
    assert {item["title"] for item in response.json()["items"]} == {
        "Alpha campaign",
        "Internal needle",
    }

    response = await client.get(REPORTS, params={"origin": "internal"})
    assert [item["title"] for item in response.json()["items"]] == ["Internal needle"]

    response = await client.get(REPORTS, params={"source_name": "Vendor B"})
    assert [item["title"] for item in response.json()["items"]] == ["Beta campaign"]

    response = await client.get(
        REPORTS,
        params={"published_from": "2026-02-15", "published_to": "2026-03-15"},
    )
    assert [item["title"] for item in response.json()["items"]] == [
        "Internal needle",
        "Beta campaign",
    ]

    response = await client.get(REPORTS, params={"ai_generated": "true"})
    assert [item["title"] for item in response.json()["items"]] == ["Beta campaign"]

    first = (await client.get(REPORTS, params={"page": 1, "size": 2})).json()
    second = (await client.get(REPORTS, params={"page": 2, "size": 2})).json()
    assert first["total"] == 3 and first["pages"] == 2
    assert len(first["items"]) == 2 and len(second["items"]) == 1

    sources = (await client.get(f"{REPORTS}/sources")).json()
    assert sources == ["SOC", "Vendor A", "Vendor B"]


@pytest.mark.parametrize(
    ("filename", "content", "expected_type"),
    [
        ("document.pdf", b"%PDF-1.7\nbody", "application/pdf"),
        ("notes.md", b"# Notes\n", "text/markdown"),
        ("notes.markdown", b"# Notes\n", "text/markdown"),
        ("notes.txt", "café".encode(), "text/plain"),
    ],
)
async def test_supported_uploads(
    client: AsyncClient,
    filename: str,
    content: bytes,
    expected_type: str,
) -> None:
    report = await create_report(client, title=filename)
    response = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    attachment = response.json()
    assert attachment["original_filename"] == filename
    assert attachment["content_type"] == expected_type
    assert attachment["size_bytes"] == len(content)
    assert len(attachment["sha256"]) == 64


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("fake.pdf", b"not a pdf"),
        ("binary.txt", b"has\x00nul"),
        ("invalid.md", b"\xff\xfe"),
        ("archive.exe", b"MZ"),
    ],
)
async def test_bad_upload_sniff_is_415(
    client: AsyncClient,
    filename: str,
    content: bytes,
) -> None:
    report = await create_report(client, title=filename)
    response = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": (filename, content)},
    )
    assert response.status_code == 415


async def test_oversize_upload_is_413(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REPORT_MAX_UPLOAD_BYTES", 4)
    report = await create_report(client, title="Oversize")
    response = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("five.txt", b"12345")},
    )
    assert response.status_code == 413


async def test_empty_upload_is_422(client: AsyncClient) -> None:
    report = await create_report(client, title="Empty")
    response = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("empty.txt", b"")},
    )
    assert response.status_code == 422


async def test_filename_is_sanitized_to_bounded_basename(client: AsyncClient) -> None:
    report = await create_report(client, title="Filename")
    response = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("../../folder\\evil\x01.txt", b"safe")},
    )
    assert response.status_code == 200
    assert response.json()["original_filename"] == "evil.txt"
    assert len(response.json()["original_filename"]) <= 255


async def test_download_headers_and_replacement(client: AsyncClient) -> None:
    report = await create_report(client, title="Download")
    url = f"{REPORTS}/{report['id']}/attachment"
    assert (await client.get(url)).status_code == 404

    await client.put(url, files={"file": ("old.txt", b"old")})
    await client.put(url, files={"file": ("résumé.txt", b"new")})
    response = await client.get(url)
    assert response.status_code == 200
    assert response.content == b"new"
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.txt"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert response.headers["cache-control"] == "private, no-store"

    response = await client.delete(url)
    assert response.status_code == 204
    assert (await client.get(url)).status_code == 404
    assert (await client.delete(url)).status_code == 404


async def test_attachment_content_is_deferred(db_session: AsyncSession) -> None:
    report = Report(title="Deferred", origin="internal")
    db_session.add(report)
    await db_session.flush()
    db_session.add(
        ReportAttachment(
            report_id=report.id,
            original_filename="deferred.txt",
            content_type="text/plain",
            size_bytes=4,
            sha256="0" * 64,
            content=b"data",
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    loaded = await report_service.get_report(db_session, report.id)
    assert loaded is not None and loaded.attachment is not None
    assert "content" in inspect(loaded.attachment).unloaded


async def test_link_unlink_both_directions_and_export_unchanged(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    observable = Observable(
        type=ObservableType.DOMAIN_NAME,
        value="linked.example",
        confidence_score=87,
    )
    db_session.add(observable)
    await db_session.commit()
    report = await create_report(client, title="Linked")
    export_before = (await client.get("/api/v1/export/json")).json()

    url = f"{REPORTS}/{report['id']}/observables"
    response = await client.post(url, json={"observable_id": str(observable.id)})
    assert response.status_code == 201
    assert response.json()["value"] == "linked.example"
    assert (await client.post(url, json={"observable_id": str(observable.id)})).status_code == 200

    detail = (await client.get(f"{REPORTS}/{report['id']}")).json()
    assert [item["id"] for item in detail["observables"]] == [str(observable.id)]
    reverse = (await client.get(f"/api/v1/observables/{observable.id}/reports")).json()
    assert [item["id"] for item in reverse] == [report["id"]]
    export_after = (await client.get("/api/v1/export/json")).json()
    assert export_after["count"] == export_before["count"]
    assert export_after["observables"] == export_before["observables"]

    response = await client.delete(f"{url}/{observable.id}")
    assert response.status_code == 204
    assert (await client.delete(f"{url}/{observable.id}")).status_code == 404
    assert (await client.get(f"/api/v1/observables/{observable.id}/reports")).json() == []


async def test_delete_report_removes_attachment_and_links(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    observable = Observable(type=ObservableType.IP_ADDR, value="192.0.2.10")
    db_session.add(observable)
    await db_session.commit()
    report = await create_report(client, title="Cascade")
    attachment_url = f"{REPORTS}/{report['id']}/attachment"
    await client.put(attachment_url, files={"file": ("one.txt", b"one")})
    await client.post(
        f"{REPORTS}/{report['id']}/observables",
        json={"observable_id": str(observable.id)},
    )

    assert (await client.delete(f"{REPORTS}/{report['id']}")).status_code == 204
    assert await db_session.scalar(select(func.count()).select_from(ReportAttachment)) == 0
    assert await db_session.scalar(select(func.count()).select_from(report_observables)) == 0


async def test_retention_removes_stale_link_but_keeps_report_and_attachment(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 11, 1, 12)
    observable = Observable(
        type=ObservableType.IP_ADDR,
        value="198.51.100.9",
        last_seen=now - timedelta(days=181),
    )
    db_session.add(observable)
    await db_session.commit()
    report = await create_report(client, title="Retained report")
    await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("retained.txt", b"retained")},
    )
    await client.post(
        f"{REPORTS}/{report['id']}/observables",
        json={"observable_id": str(observable.id)},
    )

    assert await retention.enforce_retention(db_session, 180, now=now) == 1
    assert await db_session.scalar(select(func.count()).select_from(Report)) == 1
    assert await db_session.scalar(select(func.count()).select_from(ReportAttachment)) == 1
    assert await db_session.scalar(select(func.count()).select_from(report_observables)) == 0
    detail = (await client.get(f"{REPORTS}/{report['id']}")).json()
    assert detail["observables"] == []
    assert detail["attachment"]["original_filename"] == "retained.txt"


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", REPORTS, {"json": {"title": "No", "origin": "internal"}}),
        ("patch", f"{REPORTS}/{MISSING_ID}", {"json": {"title": "No"}}),
        ("delete", f"{REPORTS}/{MISSING_ID}", {}),
        (
            "put",
            f"{REPORTS}/{MISSING_ID}/attachment",
            {"files": {"file": ("no.txt", b"no")}},
        ),
        ("delete", f"{REPORTS}/{MISSING_ID}/attachment", {}),
        (
            "post",
            f"{REPORTS}/{MISSING_ID}/observables",
            {"json": {"observable_id": MISSING_ID}},
        ),
        ("delete", f"{REPORTS}/{MISSING_ID}/observables/{MISSING_ID}", {}),
    ],
)
async def test_analyst_forbidden_on_every_write(
    analyst_client: AsyncClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    response = await analyst_client.request(method, path, **kwargs)
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", REPORTS, {}),
        ("get", f"{REPORTS}/{MISSING_ID}", {}),
        ("get", f"{REPORTS}/{MISSING_ID}/attachment", {}),
        ("post", REPORTS, {"json": {"title": "No", "origin": "internal"}}),
        (
            "put",
            f"{REPORTS}/{MISSING_ID}/attachment",
            {"files": {"file": ("no.txt", b"no")}},
        ),
    ],
)
async def test_anonymous_requests_are_401(
    anonymous_client: AsyncClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    response = await anonymous_client.request(method, path, **kwargs)
    assert response.status_code == 401
