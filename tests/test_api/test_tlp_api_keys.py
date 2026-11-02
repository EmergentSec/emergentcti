"""TLP:RED never leaves through an API-key path (#15).

For API-key callers RED items do not exist: lists omit them before
pagination, detail and mutation endpoints answer 404 without changing
anything, and nested lists drop or redact them. Interactive sessions see all.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, insert, select

from cti.models.feed import Feed
from cti.models.observable import Observable
from cti.models.report import Report, ReportAttachment, ReportOrigin, report_observables
from cti.models.tag import observable_tags
from cti.models.user import UserRole
from tests.policy_helpers import add_feed, add_observable, non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

OBS = "/api/v1/observables"
REPORTS = "/api/v1/reports"
TAGS = "/api/v1/tags"
FEEDS = "/api/v1/feeds"
MISSING = "00000000-0000-0000-0000-000000000000"


async def _red_observable(db: AsyncSession, value: str = "203.0.113.200") -> Observable:
    feed = await add_feed(db, f"Red feed {value}", tlp="red")
    return await add_observable(db, value, feed=feed)


async def _report(
    db: AsyncSession, title: str, tlp: str | None, content: str | None = None
) -> Report:
    report = Report(title=title, origin=ReportOrigin.INTERNAL, tlp=tlp, content=content)
    db.add(report)
    await db.flush()
    db.add(
        ReportAttachment(
            report_id=report.id,
            original_filename="n.txt",
            content_type="text/plain",
            size_bytes=4,
            sha256="0" * 64,
            content=b"note",
        )
    )
    await db.commit()
    return report


async def _link(db: AsyncSession, report: Report, obs: Observable) -> None:
    await db.execute(insert(report_observables).values(report_id=report.id, observable_id=obs.id))
    await db.commit()


# ── observables ──────────────────────────────────────────────────────────


async def test_list_hides_red_before_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _red_observable(db_session, "203.0.113.201")
    await _red_observable(db_session, "203.0.113.202")
    await add_observable(db_session, "203.0.113.203")

    body = (await client.get(f"{OBS}?size=1")).json()
    assert body["total"] == 1 and body["pages"] == 1
    assert [o["value"] for o in body["items"]] == ["203.0.113.203"]
    assert (await client.get(f"{OBS}?tlp=red")).json()["total"] == 0


async def test_observable_detail_and_reports_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await _red_observable(db_session)
    for url in (f"{OBS}/{obs.id}", f"{OBS}/{obs.id}/reports"):
        response = await client.get(url)
        assert response.status_code == 404
        assert response.json()["detail"] == "Observable not found"
        assert "203.0.113.200" not in response.text


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("put", "/tags", {"tags": ["x"]}),
        ("put", "/tlp-override", {"tlp": "clear", "reason": "declassify"}),
        ("delete", "/tlp-override", None),
        ("put", "/confidence-override", {"confidence": 1}),
        ("delete", "/confidence-override", None),
        ("delete", "", None),
    ],
)
async def test_observable_mutations_404_without_change(
    client: AsyncClient,
    db_session: AsyncSession,
    method: str,
    suffix: str,
    body: dict | None,
) -> None:
    obs = await _red_observable(db_session)
    kwargs = {"json": body} if body is not None else {}
    response = await client.request(method.upper(), f"{OBS}/{obs.id}{suffix}", **kwargs)
    assert response.status_code == 404
    row = (
        await db_session.execute(
            select(Observable.tlp_override, Observable.confidence_override).where(
                Observable.id == obs.id
            )
        )
    ).one()
    assert tuple(row) == (None, None)
    assert await db_session.scalar(select(func.count()).select_from(observable_tags)) == 0


async def test_create_existing_red_value_404_without_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await _red_observable(db_session)
    response = await client.post(
        OBS, json={"type": "ip-addr", "value": "203.0.113.200", "confidence_score": 99}
    )
    assert response.status_code == 404
    stored = await db_session.scalar(
        select(Observable.manual_confidence).where(Observable.id == obs.id)
    )
    assert stored is None


async def test_api_key_change_that_makes_item_red_is_applied_not_echoed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    created = await client.post(
        OBS, json={"type": "ip-addr", "value": "203.0.113.210", "tlp": "red"}
    )
    assert created.status_code == 204 and created.content == b""
    obs = await add_observable(db_session, "203.0.113.211")
    marked = await client.put(
        f"{OBS}/{obs.id}/tlp-override", json={"tlp": "red", "reason": "named recipients"}
    )
    assert marked.status_code == 204
    stored = await db_session.scalar(
        select(Observable.manual_tlp).where(Observable.value == "203.0.113.210")
    )
    assert stored == "red"
    assert (await client.get(f"{OBS}/{obs.id}")).status_code == 404
    report = await client.post(REPORTS, json={"title": "Mine", "origin": "internal", "tlp": "red"})
    assert report.status_code == 204


async def test_visible_observable_drops_red_reports_and_redacts_sources(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await add_observable(db_session, "203.0.113.220")
    red = await _report(db_session, "Secret operation", "red")
    green = await _report(db_session, "Public writeup", "green")
    await _link(db_session, red, obs)
    await _link(db_session, green, obs)
    # Declassified by an override, so the observable itself is visible.
    async with non_admin_client(app, UserRole.admin) as admin:
        response = await admin.put(
            f"{OBS}/{obs.id}/tlp-override", json={"tlp": "green", "reason": "ok"}
        )
        assert response.status_code == 200

    reports = (await client.get(f"{OBS}/{obs.id}/reports")).json()
    assert [r["title"] for r in reports] == ["Public writeup"]
    detail = await client.get(f"{OBS}/{obs.id}")
    assert "Secret operation" not in detail.text
    assert str(red.id) not in detail.text
    report_sources = [s for s in detail.json()["tlp_sources"] if s["kind"] == "report"]
    assert {"kind": "report", "id": None, "name": "Restricted report", "tlp": "red"} in (
        report_sources
    )


# ── reports ──────────────────────────────────────────────────────────────


async def test_report_list_hides_red_before_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _report(db_session, "Red one", "red")
    await _report(db_session, "Red two", "red")
    await _report(db_session, "Amber", "amber")
    body = (await client.get(f"{REPORTS}?size=1")).json()
    assert body["total"] == 1
    assert [r["title"] for r in body["items"]] == ["Amber"]


@pytest.mark.parametrize(
    ("method", "suffix", "kwargs"),
    [
        ("get", "", {}),
        ("patch", "", {"json": {"title": "Renamed"}}),
        ("delete", "", {}),
        ("put", "/tags", {"json": {"tags": ["x"]}}),
        ("get", "/attachment", {}),
        ("delete", "/attachment", {}),
        ("put", "/attachment", {"files": {"file": ("a.txt", b"new", "text/plain")}}),
        ("post", "/extract", {}),
        (
            "post",
            "/import",
            {"json": {"confidence": 50, "items": [{"type": "ip-addr", "value": "1.2.3.4"}]}},
        ),
        ("post", "/observables", {"json": {"observable_id": MISSING}}),
        ("delete", f"/observables/{MISSING}", {}),
    ],
)
async def test_red_report_endpoints_404_without_change(
    client: AsyncClient,
    db_session: AsyncSession,
    method: str,
    suffix: str,
    kwargs: dict,
) -> None:
    report = await _report(db_session, "Named recipients", "red")
    # Read before the request: a failed attempt rolls back the shared test session.
    report_id = report.id
    response = await client.request(method.upper(), f"{REPORTS}/{report_id}{suffix}", **kwargs)
    assert response.status_code == 404
    assert "Named recipients" not in response.text
    title = await db_session.scalar(select(Report.title).where(Report.id == report_id))
    assert title == "Named recipients"
    filename = await db_session.scalar(
        select(ReportAttachment.original_filename).where(ReportAttachment.report_id == report_id)
    )
    assert filename == "n.txt"


async def test_link_or_unlink_red_observable_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    report = await _report(db_session, "Visible", "amber")
    red_obs = await _red_observable(db_session)
    linked = await client.post(
        f"{REPORTS}/{report.id}/observables", json={"observable_id": str(red_obs.id)}
    )
    assert linked.status_code == 404
    # The failed attempt rolled back the shared test session; reload the fixtures.
    await db_session.refresh(report)
    await db_session.refresh(red_obs)
    await _link(db_session, report, red_obs)
    unlinked = await client.delete(f"{REPORTS}/{report.id}/observables/{red_obs.id}")
    assert unlinked.status_code == 404


async def test_visible_report_detail_strips_red_observables(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    report = await _report(db_session, "Visible", "amber")
    await _link(db_session, report, await _red_observable(db_session, "203.0.113.230"))
    await _link(db_session, report, await add_observable(db_session, "203.0.113.231"))
    detail = (await client.get(f"{REPORTS}/{report.id}")).json()
    assert [o["value"] for o in detail["observables"]] == ["203.0.113.231"]

    async with non_admin_client(app) as user:
        full = (await user.get(f"{REPORTS}/{report.id}")).json()
    assert {o["value"] for o in full["observables"]} == {"203.0.113.230", "203.0.113.231"}


_RED_VALUE = "203.0.113.240"
_NEW_VALUE = "203.0.113.241"
_IMPORT = {
    "confidence": 60,
    "items": [{"type": "ip-addr", "value": _RED_VALUE}, {"type": "ip-addr", "value": _NEW_VALUE}],
}


async def _extract_fixture(db: AsyncSession) -> tuple[Observable, Report]:
    red_obs = await _red_observable(db, _RED_VALUE)
    report = await _report(db, "Visible", "green", content=f"Seen: {_RED_VALUE} and {_NEW_VALUE}")
    return red_obs, report


async def test_extract_previews_red_match_as_new(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    red_obs, report = await _extract_fixture(db_session)
    await _link(db_session, report, red_obs)  # would show already_attributed

    preview = (await client.post(f"{REPORTS}/{report.id}/extract")).json()
    by_value = {c["value"]: c for c in preview["candidates"]}
    # Indistinguishable from a value that does not exist.
    assert {k: v for k, v in by_value[_RED_VALUE].items() if k not in ("value", "original")} == {
        k: v for k, v in by_value[_NEW_VALUE].items() if k not in ("value", "original")
    }
    assert by_value[_RED_VALUE]["status"] == "new"
    assert by_value[_RED_VALUE]["already_attributed"] is False
    assert preview["counts"] == {"total": 2, "new": 2, "existing": 0, "invalid": 0}
    assert str(red_obs.id) not in str(preview)


async def test_extract_session_still_sees_red_match_as_existing(
    app: FastAPI, db_session: AsyncSession
) -> None:
    red_obs, report = await _extract_fixture(db_session)
    async with non_admin_client(app, UserRole.admin) as admin:
        preview = (await admin.post(f"{REPORTS}/{report.id}/extract")).json()
    by_value = {c["value"]: c for c in preview["candidates"]}
    assert by_value[_RED_VALUE]["status"] == "existing"
    assert by_value[_RED_VALUE]["existing_observable_id"] == str(red_obs.id)
    assert preview["counts"]["existing"] == 1


async def test_import_skips_red_match_without_touching_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    red_obs, report = await _extract_fixture(db_session)
    before = await db_session.scalar(
        select(Observable.confidence_score).where(Observable.id == red_obs.id)
    )

    result = await client.post(f"{REPORTS}/{report.id}/import", json=_IMPORT)
    assert result.status_code == 200, result.text
    body = result.json()
    # Counters cover only what the key can see; the RED value is skipped
    # with a generic reason, not linked, and not duplicated.
    assert (body["created"], body["attributed_existing"], body["already_attributed"]) == (1, 0, 0)
    assert [o["value"] for o in body["observables"]] == [_NEW_VALUE]
    assert body["skipped"] == [{"type": "ip-addr", "value": _RED_VALUE, "reason": "not_importable"}]
    assert str(red_obs.id) not in result.text
    assert "red" not in result.text.lower()

    red_id = red_obs.id
    db_session.expire_all()
    links = await db_session.scalar(
        select(func.count())
        .select_from(report_observables)
        .where(report_observables.c.observable_id == red_id)
    )
    assert links == 0
    after = await db_session.scalar(
        select(Observable.confidence_score).where(Observable.id == red_id)
    )
    assert after == before
    copies = await db_session.scalar(
        select(func.count()).select_from(Observable).where(Observable.value == _RED_VALUE)
    )
    assert copies == 1


async def test_import_session_attributes_red_match(app: FastAPI, db_session: AsyncSession) -> None:
    red_obs, report = await _extract_fixture(db_session)
    async with non_admin_client(app, UserRole.admin) as admin:
        result = await admin.post(f"{REPORTS}/{report.id}/import", json=_IMPORT)
    assert result.status_code == 200, result.text
    body = result.json()
    assert (body["created"], body["attributed_existing"], body["skipped"]) == (1, 1, [])
    assert str(red_obs.id) in {o["id"] for o in body["observables"]}


# ── feeds ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("new_tlp", [None, "clear", "amber+strict"])
async def test_api_key_cannot_declassify_red_feed(
    client: AsyncClient, db_session: AsyncSession, new_tlp: str | None
) -> None:
    feed = await add_feed(db_session, "Red feed", tlp="red")
    response = await client.put(
        f"{FEEDS}/{feed.id}", json={"tlp": new_tlp, "tlp_change_reason": "declassify"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Declassifying a TLP:RED feed requires an interactive admin session"
    )
    feed_id = feed.id
    db_session.expire_all()
    assert await db_session.scalar(select(Feed.tlp).where(Feed.id == feed_id)) == "red"


async def test_api_key_cannot_delete_red_feed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, "Red feed", tlp="red")
    obs = await add_observable(db_session, "203.0.113.250", feed=feed)
    obs_id = obs.id
    response = await client.delete(f"{FEEDS}/{feed.id}")
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Deleting a TLP:RED feed requires an interactive admin session"
    )
    feed_id = feed.id
    db_session.expire_all()
    assert await db_session.scalar(select(Feed.id).where(Feed.id == feed_id)) == feed_id
    assert (await client.get(f"{OBS}/{obs_id}")).status_code == 404


async def test_api_key_may_make_other_edits_to_red_feed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, "Red feed", tlp="red")
    response = await client.put(f"{FEEDS}/{feed.id}", json={"description": "renamed", "tlp": "red"})
    assert response.status_code == 200, response.text
    assert response.json()["tlp"] == "red"
    assert response.json()["description"] == "renamed"


async def test_session_admin_may_declassify_red_feed(
    app: FastAPI, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, "Red feed", tlp="red")
    async with non_admin_client(app, UserRole.admin) as admin:
        response = await admin.put(
            f"{FEEDS}/{feed.id}", json={"tlp": "green", "tlp_change_reason": "declassify"}
        )
    assert response.status_code == 200, response.text
    assert response.json()["tlp"] == "green"


# ── interactive sessions and aggregates are unaffected ───────────────────


async def test_interactive_user_sees_red_items(app: FastAPI, db_session: AsyncSession) -> None:
    obs = await _red_observable(db_session)
    report = await _report(db_session, "Named recipients", "red")
    async with non_admin_client(app) as user:
        assert (await user.get(f"{OBS}/{obs.id}")).json()["effective_tlp"] == "red"
        assert (await user.get(f"{OBS}?tlp=red")).json()["total"] == 1
        assert (await user.get(f"{REPORTS}/{report.id}")).status_code == 200
        assert (await user.get(f"{REPORTS}?tlp=red")).json()["total"] == 1
        attachment = await user.get(f"{REPORTS}/{report.id}/attachment")
        assert attachment.status_code == 200
        assert attachment.headers["X-TLP-Marking"] == "red"


async def test_aggregates_may_count_red(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await _red_observable(db_session)
    async with non_admin_client(app, UserRole.admin) as admin:
        await admin.put(f"{OBS}/{obs.id}/tags", json={"tags": ["red-only"]})
    tags = (await client.get(TAGS)).json()
    assert tags == [
        {"id": tags[0]["id"], "name": "red-only", "observable_count": 1, "report_count": 0}
    ]


async def test_missing_ids_still_404(client: AsyncClient) -> None:
    assert (await client.get(f"{OBS}/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"{REPORTS}/{uuid.uuid4()}")).status_code == 404
