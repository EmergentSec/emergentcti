"""TLP enforcement in exports (#15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from cti.models.observable import ObservableType
from cti.models.user import UserRole
from tests.policy_helpers import (
    NO_TLP_EXCLUSIONS,
    add_feed,
    add_observable,
    allow,
    non_admin_client,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

EXPORT = "/api/v1/export"
PROFILES = f"{EXPORT}/profiles"
OBS = "/api/v1/observables"
IP = ObservableType.IP_ADDR


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


async def _seed_markings(db: AsyncSession) -> dict[str, str]:
    """One IP observable per effective marking; returns marking -> value."""
    values: dict[str, str] = {}
    now = datetime.now(UTC)
    for i, marking in enumerate([None, "clear", "green", "amber", "amber+strict", "red"]):
        feed = await add_feed(db, f"Feed {marking}", tlp=marking)
        value = f"203.0.113.{10 + i}"
        await add_observable(db, value, feed=feed, last_seen=now - timedelta(minutes=i))
        values[marking or "unspecified"] = value
    return values


# ── ad-hoc exports (internal scope) ──────────────────────────────────────


async def test_red_excluded_from_all_ad_hoc_exports(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    values = await _seed_markings(db_session)
    red = values["red"]
    internal = {v for k, v in values.items() if k != "red"}

    blocklist = await client.get(f"{EXPORT}/blocklist/ip-addr")
    assert set(blocklist.text.split("\n")) == internal
    assert blocklist.headers["X-TLP-Excluded"] == "1"

    text = await client.get(f"{EXPORT}/text")
    assert set(text.text.split("\n")) == internal
    assert text.headers["X-TLP-Excluded"] == "1"

    data = await client.get(f"{EXPORT}/json")
    body = data.json()
    assert {o["value"] for o in body["observables"]} == internal
    assert red not in data.text
    assert data.headers["X-TLP-Excluded"] == "1"
    markings = {o["value"]: o["tlp"] for o in body["observables"]}
    assert markings[values["unspecified"]] is None
    assert markings[values["amber+strict"]] == "amber+strict"


async def test_red_excluded_even_after_cached_blocklist(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    obs = await add_observable(db_session, "203.0.113.50")
    await add_observable(db_session, "203.0.113.51")
    url = f"{EXPORT}/blocklist/ip-addr"

    first = await client.get(url)
    assert first.headers["X-Cache"] == "MISS"
    assert first.text == "203.0.113.50\n203.0.113.51"
    assert any("203.0.113.50" in v for v in fake_cache.values())

    # Mark RED while the cached list still contains the value.
    response = await client.put(
        f"{OBS}/{obs.id}/tlp-override", json={"tlp": "red", "reason": "named recipients"}
    )
    assert response.status_code == 204  # applied; RED is not echoed to an API key
    # The fake cache is not invalidated, so the pre-policy entry survives.
    assert list(fake_cache.values()) == ["203.0.113.50\n203.0.113.51"]

    cached = await client.get(url)
    assert cached.headers["X-Cache"] == "HIT"
    assert cached.text == "203.0.113.51"
    assert cached.headers["X-TLP-Excluded"] == "1"

    # Clearing the override is reflected on the next request too. (A RED item
    # is invisible to API keys, so an interactive admin clears it.)
    async with non_admin_client(app, UserRole.admin) as admin:
        assert (await admin.delete(f"{OBS}/{obs.id}/tlp-override")).status_code == 200
    again = await client.get(url)
    assert again.headers["X-Cache"] == "HIT"
    assert again.text == "203.0.113.50\n203.0.113.51"
    assert again.headers["X-TLP-Excluded"] == "0"


async def test_red_excluded_from_json_and_text_after_prior_responses(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    feed = await add_feed(db_session, "Becomes red")
    await add_observable(db_session, "203.0.113.60", feed=feed)
    assert "203.0.113.60" in (await client.get(f"{EXPORT}/json")).text
    assert "203.0.113.60" in (await client.get(f"{EXPORT}/text")).text

    await client.put(f"/api/v1/feeds/{feed.id}", json={"tlp": "red"})
    assert "203.0.113.60" not in (await client.get(f"{EXPORT}/json")).text
    assert "203.0.113.60" not in (await client.get(f"{EXPORT}/text")).text
    assert "203.0.113.60" not in (await client.get(f"{EXPORT}/blocklist/ip-addr")).text


async def test_tlp_filter_applies_before_limit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    red_feed = await add_feed(db_session, "Red", tlp="red")
    now = datetime.now(UTC)
    # The newest rows are RED; a limit of 2 must still return 2 shareable rows.
    for i in range(3):
        await add_observable(db_session, f"198.51.100.{i}", feed=red_feed, last_seen=now)
    await add_observable(db_session, "198.51.100.10", last_seen=now - timedelta(hours=1))
    await add_observable(db_session, "198.51.100.11", last_seen=now - timedelta(hours=2))
    await add_observable(db_session, "198.51.100.12", last_seen=now - timedelta(hours=3))

    response = await client.get(f"{EXPORT}/json?limit=2")
    body = response.json()
    assert [o["value"] for o in body["observables"]] == ["198.51.100.10", "198.51.100.11"]
    # Counted over the whole filtered set, not just the scanned prefix.
    assert response.headers["X-TLP-Excluded"] == "3"


async def test_allowlist_and_tlp_are_independent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    red_feed = await add_feed(db_session, "Red", tlp="red")
    await add_observable(db_session, "203.0.113.70", feed=red_feed)  # red + allowlisted
    await add_observable(db_session, "203.0.113.71", feed=red_feed)  # red only
    await add_observable(db_session, "203.0.113.72")  # allowlisted only
    await add_observable(db_session, "203.0.113.73")  # exported
    await allow(client, "exact", "203.0.113.70", "ip-addr")
    await allow(client, "exact", "203.0.113.72", "ip-addr")

    for url in [f"{EXPORT}/blocklist/ip-addr", f"{EXPORT}/text"]:
        response = await client.get(url)
        assert response.text == "203.0.113.73"
        # Only rows that pass the allowlist count against TLP.
        assert response.headers["X-TLP-Excluded"] == "1"
    data = await client.get(f"{EXPORT}/json")
    assert [o["value"] for o in data.json()["observables"]] == ["203.0.113.73"]
    assert data.headers["X-TLP-Excluded"] == "1"

    # Removing RED does not bypass the allowlist, and vice versa.
    profile = await _profile(client, "Both", "text", destination="internal")
    preview = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    assert preview["count"] == 1
    assert preview["excluded_allowlisted"] == 2
    assert preview["excluded_by_tlp"] == {**NO_TLP_EXCLUSIONS, "red": 1}


async def test_ad_hoc_exports_accept_tag_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await add_observable(db_session, "203.0.113.80")
    b = await add_observable(db_session, "203.0.113.81")
    await add_observable(db_session, "203.0.113.82")
    await client.put(f"{OBS}/{a.id}/tags", json={"tags": ["apt-1"]})
    await client.put(f"{OBS}/{b.id}/tags", json={"tags": ["Phishing"]})

    query = "tag=apt-1&tag=phishing"
    blocklist = await client.get(f"{EXPORT}/blocklist/ip-addr?{query}")
    assert blocklist.text == "203.0.113.80\n203.0.113.81"
    text = await client.get(f"{EXPORT}/text?tag=APT-1")
    assert text.text == "203.0.113.80"
    data = (await client.get(f"{EXPORT}/json?tag=phishing")).json()
    assert [o["value"] for o in data["observables"]] == ["203.0.113.81"]
    assert data["observables"][0]["tags"] == ["phishing"]
    assert data["filters"]["tags"] == ["phishing"]
    assert (await client.get(f"{EXPORT}/json?tag=bad%20tag!")).status_code == 422


async def test_cached_blocklist_keys_include_tags(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    a = await add_observable(db_session, "203.0.113.90")
    await add_observable(db_session, "203.0.113.91")
    await client.put(f"{OBS}/{a.id}/tags", json={"tags": ["x"]})
    all_values = await client.get(f"{EXPORT}/blocklist/ip-addr")
    tagged = await client.get(f"{EXPORT}/blocklist/ip-addr?tag=x")
    assert all_values.text == "203.0.113.90\n203.0.113.91"
    assert tagged.text == "203.0.113.90"
    assert tagged.headers["X-Cache"] == "MISS"


# ── unchanged behavior when nothing is marked ────────────────────────────


async def test_exports_unchanged_when_nothing_is_marked(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    """Rollout: all markings NULL and profiles internal -> pre-#15 output."""
    feed = await add_feed(db_session, "Legacy")
    now = datetime.now(UTC)
    await add_observable(db_session, "203.0.113.2", feed=feed, last_seen=now)
    await add_observable(db_session, "203.0.113.1", feed=feed, last_seen=now - timedelta(minutes=1))
    await add_observable(
        db_session, "evil.example", ObservableType.DOMAIN_NAME, last_seen=now - timedelta(minutes=2)
    )
    await add_observable(db_session, "203.0.113.3", confidence=10, last_seen=now)
    await allow(client, "exact", "203.0.113.2", "ip-addr")

    blocklist = await client.get(f"{EXPORT}/blocklist/ip-addr")
    assert blocklist.text == "203.0.113.1"
    assert blocklist.headers["X-Observable-Count"] == "1"
    cached = await client.get(f"{EXPORT}/blocklist/ip-addr")
    assert cached.headers["X-Cache"] == "HIT" and cached.text == "203.0.113.1"

    text = await client.get(f"{EXPORT}/text")
    assert text.text == "203.0.113.3\n203.0.113.1\nevil.example"
    assert text.headers["X-TLP-Excluded"] == "0"

    data = (await client.get(f"{EXPORT}/json?confidence_min=50")).json()
    assert data["filters"] == {"confidence_min": 50}
    assert [
        {k: v for k, v in o.items() if k not in {"tlp", "tags"}} for o in data["observables"]
    ] == [
        {
            "type": "ip-addr",
            "value": "203.0.113.1",
            "confidence_score": 80,
            "last_seen": data["observables"][0]["last_seen"],
            "sources": ["Legacy"],
        },
        {
            "type": "domain-name",
            "value": "evil.example",
            "confidence_score": 80,
            "last_seen": data["observables"][1]["last_seen"],
            "sources": [],
        },
    ]
    assert all(o["tlp"] is None and o["tags"] == [] for o in data["observables"])

    profile = await _profile(client, "Legacy JSON", "json", confidence_min=0)
    assert profile["destination"] == "internal" and profile["tags"] == []
    download = (await client.get(f"{PROFILES}/{profile['id']}/download")).json()
    assert download["filters"] == {"profile": "Legacy JSON", "confidence_min": 0}
    assert [o["value"] for o in download["observables"]] == [
        "203.0.113.3",
        "203.0.113.1",
        "evil.example",
    ]
    preview = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    assert preview["count"] == 3
    assert preview["excluded_by_tlp"] == NO_TLP_EXCLUSIONS


# ── export profiles ──────────────────────────────────────────────────────


async def _profile(client: AsyncClient, name: str, fmt: str, **extra: object) -> dict:
    body = {"name": name, "format": fmt, "confidence_min": 0, **extra}
    response = await client.post(PROFILES, json=body)
    assert response.status_code == 201, response.text
    return response.json()


EXPECTED_PROFILE = {
    "internal": {"unspecified", "clear", "green", "amber", "amber+strict"},
    "community": {"clear", "green"},
    "public": {"clear"},
}


@pytest.mark.parametrize("destination", ["internal", "community", "public"])
@pytest.mark.parametrize("fmt", ["text", "json"])
async def test_profile_destination_preview_equals_download(
    client: AsyncClient, db_session: AsyncSession, destination: str, fmt: str
) -> None:
    values = await _seed_markings(db_session)
    profile = await _profile(client, f"P-{destination}-{fmt}", fmt, destination=destination)
    assert profile["destination"] == destination

    preview = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    download = await client.get(f"{PROFILES}/{profile['id']}/download")
    if fmt == "text":
        downloaded = set(download.text.split("\n")) if download.text else set()
    else:
        downloaded = {o["value"] for o in download.json()["observables"]}

    expected = {values[m] for m in EXPECTED_PROFILE[destination]}
    assert downloaded == expected
    assert preview["count"] == len(downloaded)
    assert preview["excluded_by_tlp"] == {
        key: (0 if key in EXPECTED_PROFILE[destination] else 1) for key in NO_TLP_EXCLUSIONS
    }
    assert values["red"] not in download.text


async def test_profile_invalid_destination_rejected(client: AsyncClient) -> None:
    for destination in ["external_ai", "partners", None]:
        response = await client.post(
            PROFILES, json={"name": "x", "format": "text", "destination": destination}
        )
        assert response.status_code == 422


async def test_profile_destination_update_and_preview_shows_exclusions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    values = await _seed_markings(db_session)
    profile = await _profile(client, "Switch", "text")
    before = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    assert before["count"] == 5
    assert before["excluded_by_tlp"] == {**NO_TLP_EXCLUSIONS, "red": 1}

    updated = await client.put(f"{PROFILES}/{profile['id']}", json={"destination": "public"})
    assert updated.status_code == 200 and updated.json()["destination"] == "public"
    after = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    assert after["count"] == 1
    assert after["sample"] == [values["clear"]]
    assert after["excluded_by_tlp"] == {**{k: 1 for k in NO_TLP_EXCLUSIONS}, "clear": 0}
    assert (
        await client.put(f"{PROFILES}/{profile['id']}", json={"destination": None})
    ).status_code == 422


async def test_cached_red_value_withheld_after_it_drifts_out_of_filters(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str]
) -> None:
    """A cached candidate that no longer matches the filters is still TLP-checked."""
    obs = await add_observable(db_session, "203.0.113.95", confidence=90)
    await add_observable(db_session, "203.0.113.96", confidence=90)
    url = f"{EXPORT}/blocklist/ip-addr?confidence_min=80&max_age_days=1"
    assert (await client.get(url)).text == "203.0.113.95\n203.0.113.96"

    # Marked RED, then decays below confidence_min and ages past max_age_days
    # while the pre-policy cache entry still lists it.
    await client.put(f"{OBS}/{obs.id}/tlp-override", json={"tlp": "red", "reason": "r"})
    obs.confidence_score = 10
    obs.last_seen = datetime.now(UTC) - timedelta(days=30)
    await db_session.commit()

    cached = await client.get(url)
    assert cached.headers["X-Cache"] == "HIT"
    assert cached.text == "203.0.113.96"
    assert cached.headers["X-TLP-Excluded"] == "1"
