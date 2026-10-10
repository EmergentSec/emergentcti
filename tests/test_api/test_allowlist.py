"""Allowlist API, observable status, and suppression across every export."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from tests.policy_helpers import add_feed, add_observable, allow, non_admin_client

DOMAIN = ObservableType.DOMAIN_NAME
URL = ObservableType.URL


# ── CRUD & validation ────────────────────────────────────────────────────


async def test_list_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/allowlist")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_canonicalizes_and_lists(client: AsyncClient) -> None:
    created = await allow(client, "cidr", "10.9.8.7/8", reason="  corp range  ")
    assert created["kind"] == "cidr"
    assert created["value"] == "10.0.0.0/8"
    assert created["observable_type"] == "ip-addr"
    assert created["reason"] == "corp range"
    assert uuid.UUID(created["id"])
    assert created["created_at"] and created["updated_at"]

    suffix = await allow(client, "domain_suffix", "Example.COM.")
    assert (suffix["value"], suffix["observable_type"]) == ("example.com", "domain-name")

    exact = await allow(client, "exact", "2001:0db8::0001", "ip-addr")
    assert exact["value"] == "2001:db8::1"

    listed = (await client.get("/api/v1/allowlist")).json()
    assert {e["id"] for e in listed} == {created["id"], suffix["id"], exact["id"]}


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "exact", "value": "1.2.3.4", "reason": "r"},  # missing type
        {"kind": "exact", "value": "nope", "observable_type": "ip-addr", "reason": "r"},
        {"kind": "exact", "value": "10.0.0.0/24", "observable_type": "ip-addr", "reason": "r"},
        {"kind": "cidr", "value": "example.com", "reason": "r"},
        {"kind": "cidr", "value": "10.0.0.0/40", "reason": "r"},
        {"kind": "cidr", "value": "10.0.0.0/8", "observable_type": "url", "reason": "r"},
        {"kind": "domain_suffix", "value": "*.example.com", "reason": "r"},
        {"kind": "domain_suffix", "value": "example.com", "observable_type": "url", "reason": "r"},
        {"kind": "domain_suffix", "value": "example.com", "reason": "   "},
        {"kind": "domain_suffix", "value": "example.com", "reason": "x" * 501},
        {"kind": "domain_suffix", "value": "example.com"},  # reason required
        {"kind": "regex", "value": ".*", "reason": "r"},
        {"kind": "exact", "value": "", "observable_type": "url", "reason": "r"},
    ],
)
async def test_create_rejects_invalid(client: AsyncClient, body: dict) -> None:
    response = await client.post("/api/v1/allowlist", json=body)
    assert response.status_code == 422, response.text
    assert (await client.get("/api/v1/allowlist")).json() == []


async def test_multibyte_value_over_byte_limit_is_422_not_500(client: AsyncClient) -> None:
    # 2048 characters passes the schema's length cap but is 8192 UTF-8 bytes,
    # wider than a PostgreSQL unique-index key can hold.
    body = {"kind": "exact", "value": "😀" * 2048, "observable_type": "url", "reason": "r"}
    response = await client.post("/api/v1/allowlist", json=body)
    assert response.status_code == 422
    assert "2048 bytes" in response.json()["detail"]
    assert (await client.get("/api/v1/allowlist")).json() == []

    body["value"] = "é" * 1024  # exactly 2048 bytes
    assert (await client.post("/api/v1/allowlist", json=body)).status_code == 201


async def test_policy_errors_are_readable_strings(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/allowlist", json={"kind": "cidr", "value": "nope", "reason": "r"}
    )
    assert response.status_code == 422
    assert "CIDR" in response.json()["detail"]


async def test_duplicate_canonical_policy_conflicts(client: AsyncClient) -> None:
    await allow(client, "cidr", "10.0.0.0/8")
    for value in ("10.0.0.0/8", "10.200.1.1/8"):
        response = await client.post(
            "/api/v1/allowlist", json={"kind": "cidr", "value": value, "reason": "again"}
        )
        assert response.status_code == 409
        assert isinstance(response.json()["detail"], str)

    await allow(client, "domain_suffix", "example.com")
    response = await client.post(
        "/api/v1/allowlist",
        json={"kind": "domain_suffix", "value": "EXAMPLE.com.", "reason": "again"},
    )
    assert response.status_code == 409
    assert len((await client.get("/api/v1/allowlist")).json()) == 2


async def test_same_value_different_kind_or_type_is_not_duplicate(client: AsyncClient) -> None:
    await allow(client, "domain_suffix", "example.com")
    await allow(client, "exact", "example.com", "domain-name")
    await allow(client, "exact", "example.com", "url")
    assert len((await client.get("/api/v1/allowlist")).json()) == 3


async def test_delete(client: AsyncClient) -> None:
    created = await allow(client, "cidr", "10.0.0.0/8")
    assert (await client.delete(f"/api/v1/allowlist/{created['id']}")).status_code == 204
    assert (await client.get("/api/v1/allowlist")).json() == []
    assert (await client.delete(f"/api/v1/allowlist/{created['id']}")).status_code == 404


async def test_no_edit_route(client: AsyncClient) -> None:
    created = await allow(client, "cidr", "10.0.0.0/8")
    response = await client.put(f"/api/v1/allowlist/{created['id']}", json={"reason": "new"})
    assert response.status_code == 405


# ── auth ─────────────────────────────────────────────────────────────────


async def test_requires_authentication(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        assert (await anon.get("/api/v1/allowlist")).status_code == 401
        response = await anon.post(
            "/api/v1/allowlist", json={"kind": "cidr", "value": "10.0.0.0/8", "reason": "r"}
        )
        assert response.status_code == 401


async def test_non_admin_can_read_but_not_mutate(client: AsyncClient, app: FastAPI) -> None:
    created = await allow(client, "cidr", "10.0.0.0/8")
    async with non_admin_client(app) as user:
        listed = await user.get("/api/v1/allowlist")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        response = await user.post(
            "/api/v1/allowlist", json={"kind": "cidr", "value": "172.16.0.0/12", "reason": "r"}
        )
        assert response.status_code == 403
        assert (await user.delete(f"/api/v1/allowlist/{created['id']}")).status_code == 403

    assert len((await client.get("/api/v1/allowlist")).json()) == 1


# ── observable status (derived, reversible) ──────────────────────────────


async def test_observable_status_in_list_and_detail(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    hit = await add_observable(db_session, "10.1.2.3")
    miss = await add_observable(db_session, "8.8.8.8")

    detail = (await client.get(f"/api/v1/observables/{hit.id}")).json()
    assert detail["allowlisted"] is False
    assert detail["allowlist_entry_ids"] == []

    wide = await allow(client, "cidr", "10.0.0.0/8")
    exact = await allow(client, "exact", "10.1.2.3", "ip-addr")

    detail = (await client.get(f"/api/v1/observables/{hit.id}")).json()
    assert detail["allowlisted"] is True
    assert set(detail["allowlist_entry_ids"]) == {wide["id"], exact["id"]}

    items = {o["id"]: o for o in (await client.get("/api/v1/observables")).json()["items"]}
    assert items[str(hit.id)]["allowlisted"] is True
    assert set(items[str(hit.id)]["allowlist_entry_ids"]) == {wide["id"], exact["id"]}
    assert items[str(miss.id)]["allowlisted"] is False
    assert items[str(miss.id)]["allowlist_entry_ids"] == []

    # Removing one of several matching rules keeps it allowlisted; removing all restores it.
    await client.delete(f"/api/v1/allowlist/{exact['id']}")
    detail = (await client.get(f"/api/v1/observables/{hit.id}")).json()
    assert detail["allowlist_entry_ids"] == [wide["id"]]
    await client.delete(f"/api/v1/allowlist/{wide['id']}")
    detail = (await client.get(f"/api/v1/observables/{hit.id}")).json()
    assert detail["allowlisted"] is False


async def test_allowlisting_keeps_observables_and_sources(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session)
    obs = await add_observable(db_session, "10.1.2.3", feed=feed)
    await allow(client, "cidr", "10.0.0.0/8")

    listed = (await client.get("/api/v1/observables")).json()
    assert listed["total"] == 1
    assert listed["items"][0]["source_count"] == 1
    assert (await db_session.execute(select(func.count(Observable.id)))).scalar_one() == 1
    assert (await db_session.execute(select(func.count(ObservableSource.id)))).scalar_one() == 1
    assert (await client.get(f"/api/v1/observables/{obs.id}")).status_code == 200


# ── suppression across every export ──────────────────────────────────────


async def _all_exports(client: AsyncClient) -> dict[str, set[str]]:
    blocklist = await client.get("/api/v1/export/blocklist/ip-addr?confidence_min=0")
    domains = await client.get("/api/v1/export/blocklist/domain-name?confidence_min=0")
    text = await client.get("/api/v1/export/text")
    data = (await client.get("/api/v1/export/json")).json()
    assert data["count"] == len(data["observables"])
    return {
        "blocklist": set(filter(None, blocklist.text.split("\n"))),
        "domains": set(filter(None, domains.text.split("\n"))),
        "text": set(filter(None, text.text.split("\n"))),
        "json": {o["value"] for o in data["observables"]},
    }


async def test_all_exports_suppress_and_restore(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.1.2.3")
    await add_observable(db_session, "203.0.113.5")
    await add_observable(db_session, "2001:db8::1")
    await add_observable(db_session, "cdn.example.com", DOMAIN)
    await add_observable(db_session, "badexample.com", DOMAIN)
    await add_observable(db_session, "https://cdn.example.com/x", URL)

    everything = {
        "10.1.2.3", "203.0.113.5", "2001:db8::1",
        "cdn.example.com", "badexample.com", "https://cdn.example.com/x",
    }
    before = await _all_exports(client)
    assert before["blocklist"] == {"10.1.2.3", "203.0.113.5", "2001:db8::1"}
    assert before["domains"] == {"cdn.example.com", "badexample.com"}
    assert before["text"] == before["json"] == everything

    cidr = await allow(client, "cidr", "10.0.0.0/8")
    v6 = await allow(client, "cidr", "2001:db8::/32")
    suffix = await allow(client, "domain_suffix", "example.com")

    after = await _all_exports(client)
    assert after["blocklist"] == {"203.0.113.5"}
    assert after["domains"] == {"badexample.com"}
    # The URL is not suppressed: no implicit host matching.
    remaining = {"203.0.113.5", "badexample.com", "https://cdn.example.com/x"}
    assert after["text"] == after["json"] == remaining

    for created in (cidr, v6, suffix):
        await client.delete(f"/api/v1/allowlist/{created['id']}")
    assert await _all_exports(client) == before


async def test_export_count_headers_reflect_suppression(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.1.2.3")
    await add_observable(db_session, "203.0.113.5")
    await allow(client, "exact", "10.1.2.3", "ip-addr")

    blocklist = await client.get("/api/v1/export/blocklist/ip-addr")
    assert blocklist.text == "203.0.113.5"
    assert blocklist.headers["X-Observable-Count"] == "1"
    text = await client.get("/api/v1/export/text")
    assert text.text == "203.0.113.5"
    assert text.headers["X-Observable-Count"] == "1"


async def test_everything_allowlisted_gives_empty_exports(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.1.2.3")
    await allow(client, "cidr", "0.0.0.0/0")
    blocklist = await client.get("/api/v1/export/blocklist/ip-addr")
    assert blocklist.text == ""
    assert blocklist.headers["X-Observable-Count"] == "0"
    assert (await client.get("/api/v1/export/json")).json()["count"] == 0


async def test_exact_ip_policy_suppresses_covering_range_in_exports(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.0.0.0/24")
    await add_observable(db_session, "192.0.2.0/24")
    created = await allow(client, "exact", "10.0.0.5", "ip-addr")

    url = "/api/v1/export/blocklist/ip-addr"
    assert (await client.get(url)).text == "192.0.2.0/24"
    exported = (await client.get("/api/v1/export/json")).json()["observables"]
    assert {o["value"] for o in exported} == {"192.0.2.0/24"}
    await client.delete(f"/api/v1/allowlist/{created['id']}")
    assert (await client.get(url)).text == "10.0.0.0/24\n192.0.2.0/24"


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/export/blocklist/ip-addr?max_age_days=1000000000",
        "/api/v1/export/json?max_age_days=1000000000",
        "/api/v1/export/text?max_age_days=1000000000",
        "/api/v1/export/json?max_age_days=0",
    ],
)
async def test_export_age_filter_is_bounded(client: AsyncClient, url: str) -> None:
    assert (await client.get(url)).status_code == 422


async def test_export_age_filter_accepts_maximum(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "203.0.113.5")
    response = await client.get("/api/v1/export/blocklist/ip-addr?max_age_days=36500")
    assert response.status_code == 200
    assert response.text == "203.0.113.5"


async def test_json_export_excludes_before_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    # The three newest rows are allowlisted; a limit applied first would return nothing useful.
    for i in range(3):
        await add_observable(db_session, f"10.0.0.{i}", last_seen=now - timedelta(minutes=i))
    for i in range(4):
        await add_observable(
            db_session, f"203.0.113.{i}", last_seen=now - timedelta(hours=1, minutes=i)
        )
    await allow(client, "cidr", "10.0.0.0/8")

    data = (await client.get("/api/v1/export/json?limit=3")).json()
    assert data["count"] == 3
    assert [o["value"] for o in data["observables"]] == [
        "203.0.113.0", "203.0.113.1", "203.0.113.2",
    ]


async def test_json_export_pages_past_allowlisted_rows(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.services import observable_service

    monkeypatch.setattr(observable_service, "_EXPORT_PAGE_SIZE", 2)
    now = datetime.now(UTC)
    for i in range(7):
        await add_observable(db_session, f"10.0.0.{i}", last_seen=now - timedelta(minutes=i))
    for i in range(5):
        await add_observable(
            db_session, f"203.0.113.{i}", last_seen=now - timedelta(hours=1, minutes=i)
        )
    await allow(client, "cidr", "10.0.0.0/8")

    limited = (await client.get("/api/v1/export/json?limit=1")).json()
    assert [o["value"] for o in limited["observables"]] == ["203.0.113.0"]

    full = (await client.get("/api/v1/export/json")).json()
    assert [o["value"] for o in full["observables"]] == [f"203.0.113.{i}" for i in range(5)]


async def test_text_export_is_not_truncated(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.services import observable_service

    monkeypatch.setattr(observable_service, "_EXPORT_PAGE_SIZE", 2)
    for i in range(9):
        await add_observable(db_session, f"203.0.113.{i}")
    response = await client.get("/api/v1/export/text")
    assert len(response.text.split("\n")) == 9


async def test_export_filters_still_apply(client: AsyncClient, db_session: AsyncSession) -> None:
    feed = await add_feed(db_session)
    await add_observable(db_session, "203.0.113.1", confidence=90, feed=feed)
    await add_observable(db_session, "203.0.113.2", confidence=40, feed=feed)
    await add_observable(db_session, "203.0.113.3", confidence=90)
    await add_observable(db_session, "10.0.0.1", confidence=90, feed=feed)
    await allow(client, "cidr", "10.0.0.0/8")

    response = await client.get(f"/api/v1/export/blocklist/ip-addr?feed_id={feed.id}")
    assert response.text == "203.0.113.1"
    data = (await client.get(f"/api/v1/export/json?confidence_min=50&feed_id={feed.id}")).json()
    assert [o["value"] for o in data["observables"]] == ["203.0.113.1"]
    assert data["observables"][0]["sources"] == ["Feed A"]


# ── cached blocklists never mask the current policy ──────────────────────


@pytest.fixture
def fake_cache(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    from cti.api.v1 import export

    store: dict[str, str] = {}

    async def cache_get(key: str) -> str | None:
        return store.get(key)

    async def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
        store[key] = value

    monkeypatch.setattr(export, "cache_get", cache_get)
    monkeypatch.setattr(export, "cache_set", cache_set)
    return store


async def test_cached_blocklist_applies_current_allowlist(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    await add_observable(db_session, "10.1.2.3")
    await add_observable(db_session, "203.0.113.5")
    url = "/api/v1/export/blocklist/ip-addr"

    first = await client.get(url)
    assert first.headers["X-Cache"] == "MISS"
    assert first.text == "10.1.2.3\n203.0.113.5"

    # Policy added while the blocklist is cached: the hit must already honour it.
    created = await allow(client, "cidr", "10.0.0.0/8")
    hit = await client.get(url)
    assert hit.headers["X-Cache"] == "HIT"
    assert hit.text == "203.0.113.5"
    assert hit.headers["X-Observable-Count"] == "1"

    # Policy removed while cached: the value comes back immediately.
    await client.delete(f"/api/v1/allowlist/{created['id']}")
    restored = await client.get(url)
    assert restored.headers["X-Cache"] == "HIT"
    assert restored.text == "10.1.2.3\n203.0.113.5"


async def test_blocklist_cached_before_feature_is_filtered(
    client: AsyncClient, fake_cache: dict[str, str]
) -> None:
    # An entry written by a pre-allowlist release, still within its TTL.
    fake_cache["blocklist:ip-addr:70:None:None"] = "10.1.2.3\n203.0.113.5"
    await allow(client, "cidr", "10.0.0.0/8")

    response = await client.get("/api/v1/export/blocklist/ip-addr")
    assert response.headers["X-Cache"] == "HIT"
    assert response.text == "203.0.113.5"


async def test_cached_empty_blocklist(client: AsyncClient, fake_cache: dict[str, str]) -> None:
    fake_cache["blocklist:ip-addr:70:None:None"] = ""
    response = await client.get("/api/v1/export/blocklist/ip-addr")
    assert response.text == ""
    assert response.headers["X-Observable-Count"] == "0"


async def test_cache_stores_pre_policy_list(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    await add_observable(db_session, "10.1.2.3")
    await add_observable(db_session, "203.0.113.5")
    await allow(client, "cidr", "10.0.0.0/8")

    response = await client.get("/api/v1/export/blocklist/ip-addr")
    assert response.text == "203.0.113.5"
    # Unfiltered in cache, so deleting the entry later needs no invalidation.
    assert fake_cache["blocklist:ip-addr:70:None:None"] == "10.1.2.3\n203.0.113.5"


# ── service-level default ────────────────────────────────────────────────


async def test_service_blocklist_applies_allowlist_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from cti.services import observable_service

    await add_observable(db_session, "10.1.2.3")
    await add_observable(db_session, "203.0.113.5")
    await allow(client, "cidr", "10.0.0.0/8")

    ip = ObservableType.IP_ADDR
    assert await observable_service.get_blocklist(db_session, ip) == ["203.0.113.5"]
    assert await observable_service.get_blocklist(db_session, ip, apply_allowlist=False) == [
        "10.1.2.3", "203.0.113.5",
    ]
