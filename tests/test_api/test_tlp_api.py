"""TLP markings over the API (#15): persistence, overrides, downgrades, filters."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from cti.core.dependencies import get_current_auth
from cti.models.report import report_observables
from cti.models.user import User, UserRole
from tests.policy_helpers import add_feed, add_observable, non_admin_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

OBS = "/api/v1/observables"
REPORTS = "/api/v1/reports"
FEEDS = "/api/v1/feeds"
MARKINGS = [None, "clear", "green", "amber", "amber+strict", "red"]


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(username="tlp-admin", password_hash="x", role=UserRole.admin, is_active=True)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def admin_client(app: FastAPI, admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    async def _auth() -> User:
        return admin_user

    app.dependency_overrides[get_current_auth] = _auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


async def _report(client: AsyncClient, **extra: object) -> dict:
    response = await client.post(REPORTS, json={"title": "Report", "origin": "internal", **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def _feed(client: AsyncClient, name: str, **extra: object) -> dict:
    response = await client.post(
        FEEDS, json={"name": name, "feed_type": "file", "enabled": False, **extra}
    )
    assert response.status_code == 201, response.text
    return response.json()


# ── each marking + Unspecified persists and round-trips ──────────────────


@pytest.mark.parametrize("marking", MARKINGS)
async def test_marking_round_trips_on_feed_report_and_observable(
    client: AsyncClient, marking: str | None
) -> None:
    feed = await _feed(client, f"Feed {marking}", tlp=marking)
    assert feed["tlp"] == marking
    assert (await client.get(f"{FEEDS}/{feed['id']}")).json()["tlp"] == marking

    report = await _report(client, tlp=marking)
    assert report["tlp"] == marking
    assert (await client.get(f"{REPORTS}/{report['id']}")).json()["tlp"] == marking
    listed = (await client.get(REPORTS)).json()["items"]
    assert [item["tlp"] for item in listed] == [marking]

    created = await client.post(
        OBS, json={"type": "domain-name", "value": "rt.example", "tlp": marking}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["manual_tlp"] == marking
    assert body["effective_tlp"] == marking
    assert body["tlp_sources"] == [{"kind": "manual", "id": None, "name": "Manual", "tlp": marking}]
    detail = (await client.get(f"{OBS}/{body['id']}")).json()
    assert detail["manual_tlp"] == marking and detail["effective_tlp"] == marking


async def test_manual_tlp_alias_is_accepted(client: AsyncClient) -> None:
    created = await client.post(
        OBS, json={"type": "domain-name", "value": "alias.example", "manual_tlp": "amber"}
    )
    assert created.status_code == 201
    assert created.json()["manual_tlp"] == "amber"


@pytest.mark.parametrize("bad", ["TLP:RED", "white", "Red", "", "amber strict"])
async def test_invalid_markings_are_rejected(client: AsyncClient, bad: str) -> None:
    assert (
        await client.post(REPORTS, json={"title": "x", "origin": "internal", "tlp": bad})
    ).status_code == 422
    assert (
        await client.post(FEEDS, json={"name": "x", "feed_type": "file", "tlp": bad})
    ).status_code == 422
    assert (
        await client.post(OBS, json={"type": "domain-name", "value": "x.example", "tlp": bad})
    ).status_code == 422


async def test_new_rows_default_to_unspecified(client: AsyncClient) -> None:
    feed = await _feed(client, "Plain")
    report = await _report(client)
    obs = (await client.post(OBS, json={"type": "ip-addr", "value": "192.0.2.1"})).json()
    assert feed["tlp"] is None
    assert report["tlp"] is None and report["tags"] == []
    assert obs["manual_tlp"] is None and obs["effective_tlp"] is None
    assert obs["tlp_override"] is None and obs["tags"] == []


async def test_tlp_sources_list_every_input(client: AsyncClient, db_session: AsyncSession) -> None:
    feed = await add_feed(db_session, "Source feed", tlp="green")
    obs = await add_observable(db_session, "198.51.100.20", feed=feed)
    report = await _report(client, tlp="amber", title="Amber report")
    await client.post(f"{REPORTS}/{report['id']}/observables", json={"observable_id": str(obs.id)})

    body = (await client.get(f"{OBS}/{obs.id}")).json()
    assert body["effective_tlp"] == "amber"
    assert body["tlp_sources"] == [
        {"kind": "feed", "id": str(feed.id), "name": "Source feed", "tlp": "green"},
        {"kind": "report", "id": report["id"], "name": "Amber report", "tlp": "amber"},
    ]


# ── reclassification override ────────────────────────────────────────────


async def test_override_set_loosen_tighten_and_clear(
    admin_client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, "Red feed", tlp="red")
    obs = await add_observable(db_session, "198.51.100.30", feed=feed)

    response = await admin_client.put(
        f"{OBS}/{obs.id}/tlp-override", json={"tlp": "clear", "reason": "  declassified  "}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["effective_tlp"] == "clear"
    assert body["tlp_override"]["tlp"] == "clear"
    assert body["tlp_override"]["reason"] == "declassified"
    assert body["tlp_override"]["set_by"] == "tlp-admin"
    assert body["tlp_override"]["set_at"]
    # The original restriction stays visible.
    assert body["tlp_sources"][0]["tlp"] == "red"

    tightened = await admin_client.put(
        f"{OBS}/{obs.id}/tlp-override", json={"tlp": "amber+strict", "reason": "internal only"}
    )
    assert tightened.json()["effective_tlp"] == "amber+strict"

    cleared = await admin_client.delete(f"{OBS}/{obs.id}/tlp-override")
    assert cleared.status_code == 200
    assert cleared.json()["tlp_override"] is None
    assert cleared.json()["effective_tlp"] == "red"
    again = await admin_client.delete(f"{OBS}/{obs.id}/tlp-override")
    assert again.status_code == 200  # idempotent


@pytest.mark.parametrize(
    "body",
    [
        {"tlp": None, "reason": "explicitly unspecified"},
        {"reason": "missing tlp"},
        {"tlp": "red"},
        {"tlp": "red", "reason": ""},
        {"tlp": "red", "reason": "   "},
        {"tlp": "red", "reason": "x" * 501},
        {"tlp": "purple", "reason": "bad"},
    ],
)
async def test_override_validation(
    client: AsyncClient, db_session: AsyncSession, body: dict
) -> None:
    obs = await add_observable(db_session, "198.51.100.31")
    response = await client.put(f"{OBS}/{obs.id}/tlp-override", json=body)
    assert response.status_code == 422


async def test_override_404_and_admin_guard(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession
) -> None:
    missing = uuid.uuid4()
    body = {"tlp": "red", "reason": "r"}
    assert (await client.put(f"{OBS}/{missing}/tlp-override", json=body)).status_code == 404
    assert (await client.delete(f"{OBS}/{missing}/tlp-override")).status_code == 404
    obs = await add_observable(db_session, "198.51.100.32")
    async with non_admin_client(app) as user:
        assert (await user.put(f"{OBS}/{obs.id}/tlp-override", json=body)).status_code == 403
        assert (await user.delete(f"{OBS}/{obs.id}/tlp-override")).status_code == 403
        # Viewing markings is not restricted.
        assert (await user.get(f"{OBS}/{obs.id}")).status_code == 200


# ── downgrades need a reason ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("old", "new", "needs_reason"),
    [
        ("red", "amber", True),
        ("green", "clear", True),
        ("clear", None, True),
        ("amber", "red", False),
        ("amber", "amber", False),
        (None, "clear", False),  # initial classification, not a downgrade
        (None, "red", False),
    ],
)
async def test_feed_and_report_downgrade_rule(
    client: AsyncClient, old: str | None, new: str | None, needs_reason: bool
) -> None:
    feed = await _feed(client, f"F {old}->{new}", tlp=old)
    report = await _report(client, tlp=old)

    feed_response = await client.put(f"{FEEDS}/{feed['id']}", json={"tlp": new})
    report_response = await client.patch(f"{REPORTS}/{report['id']}", json={"tlp": new})
    if needs_reason:
        assert feed_response.status_code == 422
        assert "tlp_change_reason" in feed_response.text
        assert report_response.status_code == 422
        assert "tlp_change_reason" in report_response.text
        # Nothing changed.
        assert (await client.get(f"{FEEDS}/{feed['id']}")).json()["tlp"] == old
        assert (await client.get(f"{REPORTS}/{report['id']}")).json()["tlp"] == old
        feed_response = await client.put(
            f"{FEEDS}/{feed['id']}", json={"tlp": new, "tlp_change_reason": "approved"}
        )
        report_response = await client.patch(
            f"{REPORTS}/{report['id']}", json={"tlp": new, "tlp_change_reason": "approved"}
        )
    assert feed_response.status_code == 200, feed_response.text
    assert feed_response.json()["tlp"] == new
    assert report_response.status_code == 200, report_response.text
    assert report_response.json()["tlp"] == new


async def test_downgrade_reason_is_trimmed_and_bounded(client: AsyncClient) -> None:
    feed = await _feed(client, "Bounded", tlp="red")
    for reason in ["   ", "x" * 501]:
        response = await client.put(
            f"{FEEDS}/{feed['id']}", json={"tlp": "clear", "tlp_change_reason": reason}
        )
        assert response.status_code == 422


async def test_downgrade_is_logged(client: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    report = await _report(client, tlp="red")
    with caplog.at_level("INFO", logger="cti.services.tlp"):
        response = await client.patch(
            f"{REPORTS}/{report['id']}", json={"tlp": "green", "tlp_change_reason": "public now"}
        )
    assert response.status_code == 200
    assert any("red -> green" in r.message and "public now" in r.message for r in caplog.records)


async def test_preconfigured_feed_tlp_is_editable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, "Preconfigured", is_preconfigured=True)
    response = await client.put(f"{FEEDS}/{feed.id}", json={"tlp": "amber"})
    assert response.status_code == 200
    assert response.json()["tlp"] == "amber"


# ── filters ──────────────────────────────────────────────────────────────


async def test_observable_tlp_filter_uses_effective_marking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    red_feed = await add_feed(db_session, "Red", tlp="red")
    green_feed = await add_feed(db_session, "Green", tlp="green")
    await add_observable(db_session, "198.51.100.40", feed=red_feed)
    await add_observable(db_session, "198.51.100.41", feed=green_feed)
    await add_observable(db_session, "198.51.100.42")  # manual, unspecified

    async def values(query: str) -> set[str]:
        response = await client.get(f"{OBS}?{query}")
        assert response.status_code == 200, response.text
        return {item["value"] for item in response.json()["items"]}

    assert await values("tlp=red") == {"198.51.100.40"}
    assert await values("tlp=unspecified") == {"198.51.100.42"}
    assert await values("tlp=red&tlp=green") == {"198.51.100.40", "198.51.100.41"}
    assert (await client.get(f"{OBS}?tlp=TLP:RED")).status_code == 422


async def test_report_tlp_filter(client: AsyncClient) -> None:
    await _report(client, tlp="red", title="R")
    await _report(client, tlp="clear", title="C")
    await _report(client, title="U")

    async def titles(query: str) -> set[str]:
        return {r["title"] for r in (await client.get(f"{REPORTS}?{query}")).json()["items"]}

    assert await titles("tlp=red") == {"R"}
    assert await titles("tlp=unspecified&tlp=clear") == {"C", "U"}


# ── attachment ───────────────────────────────────────────────────────────


async def _report_with_attachment(client: AsyncClient, tlp: str | None) -> dict:
    report = await _report(client, tlp=tlp)
    upload = await client.put(
        f"{REPORTS}/{report['id']}/attachment",
        files={"file": ("notes.txt", b"secret notes", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    return report


async def test_red_attachment_rejects_api_key(client: AsyncClient) -> None:
    report = await _report_with_attachment(client, "red")
    response = await client.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 403
    assert "TLP:RED" in response.json()["detail"]
    assert response.headers["X-TLP-Marking"] == "red"


async def test_red_attachment_allows_interactive_user(client: AsyncClient, app: FastAPI) -> None:
    report = await _report_with_attachment(client, "red")
    async with non_admin_client(app) as user:
        response = await user.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 200
    assert response.content == b"secret notes"
    assert response.headers["X-TLP-Marking"] == "red"


@pytest.mark.parametrize("marking", [None, "clear", "amber+strict"])
async def test_non_red_attachment_header_for_api_key(
    client: AsyncClient, marking: str | None
) -> None:
    report = await _report_with_attachment(client, marking)
    response = await client.get(f"{REPORTS}/{report['id']}/attachment")
    assert response.status_code == 200
    assert response.headers["X-TLP-Marking"] == (marking or "unspecified")


async def test_report_json_is_not_filtered_by_tlp(client: AsyncClient) -> None:
    report = await _report_with_attachment(client, "red")
    detail = await client.get(f"{REPORTS}/{report['id']}")
    assert detail.status_code == 200
    assert detail.json()["tlp"] == "red"
    assert detail.json()["has_attachment"] is True


async def test_linked_observable_inherits_report_marking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    report = await _report(client, tlp="red")
    obs = await add_observable(db_session, "198.51.100.50")
    await db_session.execute(
        insert(report_observables).values(report_id=uuid.UUID(report["id"]), observable_id=obs.id)
    )
    await db_session.commit()
    body = (await client.get(f"{OBS}/{obs.id}")).json()
    assert body["effective_tlp"] == "red"
    # A manual observable linked to a report: manual NULL is not an input.
    assert [s["kind"] for s in body["tlp_sources"]] == ["report"]
