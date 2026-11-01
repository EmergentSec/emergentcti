"""Report IOC extraction preview and reviewed import (issue #14 contract)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from cti.core.dependencies import get_current_auth
from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.models.report import Report, ReportAttachment, report_observables
from cti.models.user import User, UserRole
from cti.services import retention

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

REPORTS = "/api/v1/reports"
MISSING_ID = "00000000-0000-0000-0000-000000000000"
OLD = datetime(2025, 1, 2, 3, 4, 5)

CONTENT = """# Campaign notes
New C2 at hxxps[://]c2[.]evil-new[.]example/gate and drop host fresh-drop.example.
Known scanner 185.220.101.42 also seen. Linked earlier: 45.33.32.156.
Allowlisted cdn.trusted.example appears. Broken address 999.1.1.1 too.
"""


async def create_report(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    payload = {"title": "IOC report", "origin": "provider", "content": CONTENT, **overrides}
    response = await client.post(REPORTS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def make_user(db: AsyncSession, username: str, role: UserRole) -> User:
    user = User(username=username, password_hash="unused", role=role, is_active=True)
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def analyst(db_session: AsyncSession) -> User:
    return await make_user(db_session, "ioc-analyst", UserRole.user)


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    return await make_user(db_session, "ioc-admin", UserRole.admin)


async def _client_as(app: FastAPI, user: User) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate() -> User:
        return user

    app.dependency_overrides[get_current_auth] = authenticate
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


@pytest.fixture
async def analyst_client(app: FastAPI, analyst: User) -> AsyncGenerator[AsyncClient, None]:
    async for ac in _client_as(app, analyst):
        yield ac


@pytest.fixture
async def admin_client(app: FastAPI, admin: User) -> AsyncGenerator[AsyncClient, None]:
    async for ac in _client_as(app, admin):
        yield ac


@pytest.fixture
async def anonymous_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def world(db_session: AsyncSession, client: AsyncClient) -> dict[str, Any]:
    """A report plus an existing sourced observable, a manually linked one and an allowlist."""
    feed = Feed(name="Scanner feed", feed_type=FeedType.FILE)
    known = Observable(
        type=ObservableType.IP_ADDR,
        value="185.220.101.42",
        confidence_score=88,
        first_seen=OLD,
        last_seen=OLD,
    )
    linked = Observable(
        type=ObservableType.IP_ADDR,
        value="45.33.32.156",
        confidence_score=33,
        first_seen=OLD,
        last_seen=OLD,
    )
    db_session.add_all([feed, known, linked])
    await db_session.flush()
    db_session.add(ObservableSource(observable_id=known.id, feed_id=feed.id, source_confidence=88))
    db_session.add(
        AllowlistEntry(
            kind=AllowlistKind.DOMAIN_SUFFIX,
            observable_type=ObservableType.DOMAIN_NAME,
            value="trusted.example",
            reason="Our CDN",
        )
    )
    await db_session.commit()
    report = await create_report(client)
    response = await client.post(
        f"{REPORTS}/{report['id']}/observables", json={"observable_id": str(linked.id)}
    )
    assert response.status_code == 201
    # Plain ids: tests expire the session, and expired ORM attributes cannot
    # lazy-load under asyncio.
    return {"report": report, "known": known.id, "linked": linked.id, "feed": feed.id}


async def snapshot(db: AsyncSession) -> dict[str, Any]:
    observables = (
        await db.execute(
            select(
                Observable.type,
                Observable.value,
                Observable.confidence_score,
                Observable.first_seen,
                Observable.last_seen,
            ).order_by(Observable.value)
        )
    ).all()
    links = (await db.execute(select(report_observables).order_by("observable_id"))).all()
    return {
        "observables": [tuple(row) for row in observables],
        "links": [tuple(row) for row in links],
        "sources": await db.scalar(select(func.count()).select_from(ObservableSource)),
        "allowlist": await db.scalar(select(func.count()).select_from(AllowlistEntry)),
        "feeds": await db.scalar(select(func.count()).select_from(Feed)),
    }


async def link_row(db: AsyncSession, report_id: str, observable_id: Any) -> Any:
    return (
        await db.execute(
            select(report_observables).where(
                report_observables.c.report_id == uuid.UUID(str(report_id)),
                report_observables.c.observable_id == uuid.UUID(str(observable_id)),
            )
        )
    ).one_or_none()


def candidate(preview: dict[str, Any], obs_type: str, value: str) -> dict[str, Any]:
    matches = [c for c in preview["candidates"] if c["type"] == obs_type and c["value"] == value]
    assert len(matches) == 1, preview["candidates"]
    return matches[0]


# ── Extract ───────────────────────────────────────────────────────────────


async def test_extract_flags_candidates_and_performs_no_writes(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    before = await snapshot(db_session)

    response = await client.post(f"{REPORTS}/{report_id}/extract")

    assert response.status_code == 200, response.text
    assert await snapshot(db_session) == before
    preview = response.json()
    assert preview["report_id"] == report_id
    assert preview["truncated"] is False
    assert preview["sources"] == [
        {
            "kind": "content",
            "filename": None,
            "content_type": None,
            "status": "extracted",
            "reason": None,
        }
    ]

    url = candidate(preview, "url", "https://c2.evil-new.example/gate")
    assert url["status"] == "new"
    assert url["defanged"] is True
    assert url["original"] == "hxxps[://]c2[.]evil-new[.]example/gate"
    assert "New C2 at" in url["context"]
    assert url["existing_observable_id"] is None
    assert url["existing_confidence"] is None
    assert url["already_attributed"] is False

    known = candidate(preview, "ip-addr", "185.220.101.42")
    assert known["status"] == "existing"
    assert known["existing_observable_id"] == str(world["known"])
    assert known["existing_confidence"] == 88
    assert known["already_attributed"] is False

    linked = candidate(preview, "ip-addr", "45.33.32.156")
    assert linked["status"] == "existing"
    assert linked["already_attributed"] is True

    allowlisted = candidate(preview, "domain-name", "cdn.trusted.example")
    assert allowlisted["status"] == "new"
    assert allowlisted["allowlisted"] is True
    assert allowlisted["allowlist_matches"] == ["trusted.example"]
    assert candidate(preview, "domain-name", "fresh-drop.example")["allowlisted"] is False

    invalid = candidate(preview, "ip-addr", "999.1.1.1")
    assert invalid["status"] == "invalid"
    assert invalid["warnings"] == ["invalid_ip"]

    statuses = [c["status"] for c in preview["candidates"]]
    assert preview["counts"] == {
        "total": len(statuses),
        "new": statuses.count("new"),
        "existing": 2,
        "invalid": 1,
    }
    order = [(c["type"], c["value"]) for c in preview["candidates"]]
    assert order == sorted(order)


async def test_extract_reads_text_attachment_and_reports_pdf_unsupported(
    client: AsyncClient,
) -> None:
    report = await create_report(client, content=None)
    attachment = f"{REPORTS}/{report['id']}/attachment"
    await client.put(attachment, files={"file": ("iocs.md", b"Exfil to drop[.]example")})
    preview = (await client.post(f"{REPORTS}/{report['id']}/extract")).json()
    assert [s["status"] for s in preview["sources"]] == ["empty", "extracted"]
    assert preview["sources"][1]["filename"] == "iocs.md"
    assert preview["sources"][1]["content_type"] == "text/markdown"
    assert [c["value"] for c in preview["candidates"]] == ["drop.example"]

    await client.put(attachment, files={"file": ("report.pdf", b"%PDF-1.7 evil.example")})
    preview = (await client.post(f"{REPORTS}/{report['id']}/extract")).json()
    assert preview["sources"][1] == {
        "kind": "attachment",
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "status": "unsupported",
        "reason": "pdf_text_extraction_unavailable",
    }
    assert preview["candidates"] == []
    assert preview["counts"] == {"total": 0, "new": 0, "existing": 0, "invalid": 0}


async def test_extract_reports_other_attachment_types_unsupported(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    report = await create_report(client, content="Seen evil.example")
    db_session.add(
        ReportAttachment(
            report_id=uuid.UUID(report["id"]),
            original_filename="blob.bin",
            content_type="application/octet-stream",
            size_bytes=3,
            sha256="0" * 64,
            content=b"abc",
        )
    )
    await db_session.commit()
    preview = (await client.post(f"{REPORTS}/{report['id']}/extract")).json()
    assert preview["sources"][1]["status"] == "unsupported"
    assert preview["sources"][1]["reason"] == "unsupported_content_type"
    assert [c["value"] for c in preview["candidates"]] == ["evil.example"]


# ── Access control and 404 ───────────────────────────────────────────────


IMPORT_BODY = {"confidence": 50, "items": [{"type": "domain-name", "value": "evil.example"}]}


async def restricted_report_url(db: AsyncSession, path: str) -> str:
    # Created through the ORM: auth overrides apply app-wide, so the API-key
    # client cannot be used alongside the analyst client.
    report = Report(title="Restricted", origin="provider", content="evil.example")
    db.add(report)
    await db.commit()
    return f"{REPORTS}/{report.id}/{path}"


@pytest.mark.parametrize(("path", "body"), [("extract", None), ("import", IMPORT_BODY)])
async def test_anonymous_gets_401(
    anonymous_client: AsyncClient,
    db_session: AsyncSession,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    url = await restricted_report_url(db_session, path)
    before = await snapshot(db_session)
    assert (await anonymous_client.post(url, json=body)).status_code == 401
    assert await snapshot(db_session) == before


@pytest.mark.parametrize(("path", "body"), [("extract", None), ("import", IMPORT_BODY)])
async def test_analyst_gets_403(
    analyst_client: AsyncClient,
    db_session: AsyncSession,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    url = await restricted_report_url(db_session, path)
    before = await snapshot(db_session)
    assert (await analyst_client.post(url, json=body)).status_code == 403
    assert await snapshot(db_session) == before


@pytest.mark.parametrize(("path", "body"), [("extract", None), ("import", IMPORT_BODY)])
async def test_unknown_report_404(
    client: AsyncClient,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    response = await client.post(f"{REPORTS}/{MISSING_ID}/{path}", json=body)
    assert response.status_code == 404


# ── Import ───────────────────────────────────────────────────────────────


async def test_import_creates_new_with_chosen_confidence_and_no_sources(
    admin_client: AsyncClient,
    admin: User,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    sources_before = await db_session.scalar(select(func.count()).select_from(ObservableSource))
    items = [
        {"type": "url", "value": "https://c2.evil-new.example/gate"},
        {"type": "domain-name", "value": "fresh-drop.example"},
    ]

    response = await admin_client.post(
        f"{REPORTS}/{report_id}/import", json={"confidence": 64, "items": items}
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 2
    assert result["attributed_existing"] == 0
    assert result["already_attributed"] == 0
    assert [(o["type"], o["value"], o["created"]) for o in result["observables"]] == [
        ("url", "https://c2.evil-new.example/gate", True),
        ("domain-name", "fresh-drop.example", True),
    ]
    assert all(o["confidence_score"] == 64 for o in result["observables"])

    for item in result["observables"]:
        observable = await db_session.get(Observable, uuid.UUID(item["id"]), populate_existing=True)
        assert observable is not None
        assert observable.confidence_score == 64
        assert observable.first_seen is not None
        assert observable.first_seen == observable.last_seen
        row = await link_row(db_session, report_id, observable.id)
        assert row.imported_at is not None
        assert row.imported_by_id == admin.id
        assert row.analyst_confidence == 64
        assert row.source_excerpt
        assert len(row.source_excerpt) <= 500
    assert (
        "New C2 at"
        in (await link_row(db_session, report_id, result["observables"][0]["id"])).source_excerpt
    )
    assert (
        await db_session.scalar(select(func.count()).select_from(ObservableSource))
        == sources_before
    )

    detail = (await admin_client.get(f"{REPORTS}/{report_id}")).json()
    assert {o["value"] for o in detail["observables"]} >= {
        "https://c2.evil-new.example/gate",
        "fresh-drop.example",
    }


async def test_import_existing_keeps_confidence_sources_and_timestamps(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    known_id = world["known"]

    response = await client.post(
        f"{REPORTS}/{report_id}/import",
        json={"confidence": 10, "items": [{"type": "ip-addr", "value": "185.220.101.42"}]},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 0
    assert result["attributed_existing"] == 1
    assert result["observables"] == [
        {
            "id": str(known_id),
            "type": "ip-addr",
            "value": "185.220.101.42",
            "confidence_score": 88,
            "created": False,
        }
    ]
    observable = await db_session.get(Observable, known_id, populate_existing=True)
    assert observable is not None
    assert observable.confidence_score == 88
    assert observable.first_seen == OLD
    assert observable.last_seen == OLD
    sources = (
        await db_session.scalars(
            select(ObservableSource).where(ObservableSource.observable_id == known_id)
        )
    ).all()
    assert [(s.feed_id, s.source_confidence) for s in sources] == [(world["feed"], 88)]
    row = await link_row(db_session, report_id, known_id)
    assert row.analyst_confidence == 10
    assert row.imported_at is not None
    assert row.imported_by_id is None  # API-key admin has no user


async def test_import_retry_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    body = {
        "confidence": 70,
        "items": [
            {"type": "domain-name", "value": "fresh-drop.example"},
            {"type": "ip-addr", "value": "185.220.101.42"},
        ],
    }
    first = await client.post(f"{REPORTS}/{report_id}/import", json=body)
    assert first.status_code == 200
    after_first = await snapshot(db_session)

    second = await client.post(f"{REPORTS}/{report_id}/import", json={**body, "confidence": 5})

    assert second.status_code == 200, second.text
    assert second.json()["created"] == 0
    assert second.json()["attributed_existing"] == 0
    assert second.json()["already_attributed"] == 2
    assert [o["created"] for o in second.json()["observables"]] == [False, False]
    assert [o["id"] for o in second.json()["observables"]] == [
        o["id"] for o in first.json()["observables"]
    ]
    # No duplicate observable or link row, and the first import's attribution
    # (confidence 70) is left untouched.
    assert await snapshot(db_session) == after_first


async def test_import_fills_attribution_on_manual_link(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    linked_id = world["linked"]
    manual = await link_row(db_session, report_id, linked_id)
    assert manual.imported_at is None
    assert manual.analyst_confidence is None

    response = await client.post(
        f"{REPORTS}/{report_id}/import",
        json={"confidence": 42, "items": [{"type": "ip-addr", "value": "45.33.32.156"}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["attributed_existing"] == 1
    assert response.json()["already_attributed"] == 0
    row = await link_row(db_session, report_id, linked_id)
    assert row.created_at == manual.created_at
    assert row.imported_at is not None
    assert row.analyst_confidence == 42
    assert "Linked earlier" in row.source_excerpt
    links = await db_session.scalar(
        select(func.count())
        .select_from(report_observables)
        .where(report_observables.c.observable_id == linked_id)
    )
    assert links == 1
    observable = await db_session.get(Observable, linked_id, populate_existing=True)
    assert observable is not None
    assert observable.confidence_score == 33


def assert_not_a_candidate(response: Any, expected: list[tuple[int, str, str]]) -> None:
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert len(detail) == 1
    entry = detail[0]
    assert set(entry) == {"type", "loc", "msg", "items"}
    assert entry["type"] == "not_a_candidate"
    assert entry["loc"] == ["body", "items"]
    assert entry["msg"].startswith(f"{len(expected)} item(s) are not valid candidates")
    assert entry["items"] == [
        {"index": index, "type": obs_type, "value": value} for index, obs_type, value in expected
    ]
    for _, obs_type, value in expected:
        assert f"{obs_type} {value}" in entry["msg"]


@pytest.mark.parametrize(
    "bad_item",
    [
        {"type": "domain-name", "value": "not-in-report.example"},  # not in the report
        {"type": "ip-addr", "value": "999.1.1.1"},  # invalid candidate
        {"type": "domain-name", "value": "FRESH-DROP.example"},  # client normalization
        {"type": "url", "value": "hxxps[://]c2[.]evil-new[.]example/gate"},  # as written
        {"type": "ip-addr", "value": "fresh-drop.example"},  # wrong type
        {"type": "command-line", "value": "fresh-drop.example"},  # unsupported type
        {"type": "bogus", "value": "x"},
    ],
)
async def test_import_rejects_non_candidates_without_writing(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
    bad_item: dict[str, str],
) -> None:
    report_id = world["report"]["id"]
    before = await snapshot(db_session)
    items = [{"type": "domain-name", "value": "fresh-drop.example"}, bad_item]

    response = await client.post(
        f"{REPORTS}/{report_id}/import", json={"confidence": 50, "items": items}
    )

    assert_not_a_candidate(response, [(1, bad_item["type"], bad_item["value"])])
    assert await snapshot(db_session) == before


async def test_import_against_unsupported_pdf_only_report_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    report = await create_report(client, content=None)
    await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("scan.pdf", b"%PDF-1.4 evil.example 185.220.101.42")},
    )
    before = await snapshot(db_session)

    response = await client.post(
        f"{REPORTS}/{report['id']}/import",
        json={"confidence": 50, "items": [{"type": "domain-name", "value": "evil.example"}]},
    )

    assert_not_a_candidate(response, [(0, "domain-name", "evil.example")])
    assert await snapshot(db_session) == before


@pytest.mark.parametrize(
    ("body", "error_type"),
    [
        ({"confidence": 50, "items": []}, "too_short"),
        (
            {
                "confidence": 50,
                "items": [{"type": "domain-name", "value": f"h{i}.example"} for i in range(1001)],
            },
            "too_long",
        ),
        (
            {
                "confidence": 50,
                "items": [
                    {"type": "domain-name", "value": "fresh-drop.example"},
                    {"type": "domain-name", "value": "fresh-drop.example"},
                ],
            },
            "duplicate_items",
        ),
        ({"items": [{"type": "domain-name", "value": "fresh-drop.example"}]}, "missing"),
        (
            {"confidence": -1, "items": [{"type": "domain-name", "value": "fresh-drop.example"}]},
            "greater_than_equal",
        ),
        (
            {"confidence": 101, "items": [{"type": "domain-name", "value": "fresh-drop.example"}]},
            "less_than_equal",
        ),
        (
            {"confidence": "50", "items": [{"type": "domain-name", "value": "fresh-drop.example"}]},
            "int_type",
        ),
        (
            {"confidence": 50.5, "items": [{"type": "domain-name", "value": "fresh-drop.example"}]},
            "int_type",
        ),
        (
            {"confidence": True, "items": [{"type": "domain-name", "value": "fresh-drop.example"}]},
            "int_type",
        ),
    ],
)
async def test_import_body_validation_uses_fastapi_detail_shape(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
    body: dict[str, Any],
    error_type: str,
) -> None:
    before = await snapshot(db_session)
    response = await client.post(f"{REPORTS}/{world['report']['id']}/import", json=body)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["type"] == error_type
    assert isinstance(detail[0]["msg"], str)
    assert await snapshot(db_session) == before


async def test_unlink_after_import_keeps_observable_and_retention_cleans_links(
    client: AsyncClient,
    db_session: AsyncSession,
    world: dict[str, Any],
) -> None:
    report_id = world["report"]["id"]
    result = (
        await client.post(
            f"{REPORTS}/{report_id}/import",
            json={
                "confidence": 50,
                "items": [
                    {"type": "domain-name", "value": "fresh-drop.example"},
                    {"type": "ip-addr", "value": "185.220.101.42"},
                ],
            },
        )
    ).json()
    fresh_id, known_id = (o["id"] for o in result["observables"])

    response = await client.delete(f"{REPORTS}/{report_id}/observables/{fresh_id}")
    assert response.status_code == 204
    assert await link_row(db_session, report_id, fresh_id) is None
    assert await db_session.get(Observable, uuid.UUID(fresh_id), populate_existing=True) is not None

    # The known observable was last seen long ago; retention removes it and its
    # attributed link row, but never the report.
    deleted = await retention.enforce_retention(db_session, 180, now=datetime.now() + timedelta(1))
    assert deleted == 2  # known and the manually linked observable (both OLD)
    assert await link_row(db_session, report_id, known_id) is None
    assert await db_session.get(Report, uuid.UUID(report_id), populate_existing=True) is not None
