"""Flat tags (#15): normalization, endpoints, filters, profile tag filter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cti.services.tag_service import TagValidationError, normalize_tag
from tests.policy_helpers import add_observable, non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

TAGS = "/api/v1/tags"
OBS = "/api/v1/observables"
REPORTS = "/api/v1/reports"
PROFILES = "/api/v1/export/profiles"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("APT28", "apt28"),
        ("  Fancy   Bear  ", "fancy-bear"),
        ("tab\tand\nnewline", "tab-and-newline"),
        ("mitre:T1566.001", "mitre:t1566.001"),
        ("a/b_c-d.e", "a/b_c-d.e"),
        ("STRASSE", "strasse"),
        ("Straße", "strasse"),  # Unicode casefold
        ("x" * 50, "x" * 50),
    ],
)
def test_normalize_tag(raw: str, expected: str) -> None:
    assert normalize_tag(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "x" * 51, "café", "a,b", "emoji🙂", "#hash", "a+b"])
def test_normalize_tag_rejects(raw: str) -> None:
    with pytest.raises(TagValidationError):
        normalize_tag(raw)


async def test_create_list_duplicate_and_delete(client: AsyncClient) -> None:
    created = await client.post(TAGS, json={"name": "  Ransomware  "})
    assert created.status_code == 201
    assert created.json()["name"] == "ransomware"
    duplicate = await client.post(TAGS, json={"name": "RANSOMWARE"})
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == created.json()["id"]
    await client.post(TAGS, json={"name": "phishing"})
    await client.post(TAGS, json={"name": "apt-29"})

    listed = (await client.get(TAGS)).json()
    assert [t["name"] for t in listed] == ["apt-29", "phishing", "ransomware"]
    assert listed[0] == {
        "id": listed[0]["id"],
        "name": "apt-29",
        "observable_count": 0,
        "report_count": 0,
    }
    assert [t["name"] for t in (await client.get(f"{TAGS}?q=PH")).json()] == ["phishing"]
    assert (await client.get(f"{TAGS}?q=a_")).json() == []  # LIKE wildcards are literal

    assert (await client.delete(f"{TAGS}/{created.json()['id']}")).status_code == 204
    assert (await client.delete(f"{TAGS}/{created.json()['id']}")).status_code == 404


@pytest.mark.parametrize("name", ["", "x" * 51, "no spaces?", "ü"])
async def test_create_invalid_names_422(client: AsyncClient, name: str) -> None:
    response = await client.post(TAGS, json={"name": name})
    assert response.status_code == 422


async def test_admin_guards(app: FastAPI, client: AsyncClient, db_session: AsyncSession) -> None:
    tag = (await client.post(TAGS, json={"name": "guarded"})).json()
    obs = await add_observable(db_session, "192.0.2.10")
    report = (await client.post(REPORTS, json={"title": "R", "origin": "internal"})).json()
    async with non_admin_client(app) as user:
        assert (await user.get(TAGS)).status_code == 200
        assert (await user.post(TAGS, json={"name": "nope"})).status_code == 403
        assert (await user.delete(f"{TAGS}/{tag['id']}")).status_code == 403
        assert (await user.put(f"{OBS}/{obs.id}/tags", json={"tags": ["a"]})).status_code == 403
        assert (
            await user.put(f"{REPORTS}/{report['id']}/tags", json={"tags": ["a"]})
        ).status_code == 403


async def test_observable_tags_replace_normalize_and_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await add_observable(db_session, "192.0.2.20")
    response = await client.put(
        f"{OBS}/{obs.id}/tags", json={"tags": ["Zeta", "alpha", "ALPHA", " zeta "]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["tags"] == ["alpha", "zeta"]

    replaced = await client.put(f"{OBS}/{obs.id}/tags", json={"tags": ["beta"]})
    assert replaced.json()["tags"] == ["beta"]
    assert (await client.get(f"{OBS}/{obs.id}")).json()["tags"] == ["beta"]

    counts = {t["name"]: t["observable_count"] for t in (await client.get(TAGS)).json()}
    assert counts == {"alpha": 0, "beta": 1, "zeta": 0}

    cleared = await client.put(f"{OBS}/{obs.id}/tags", json={"tags": []})
    assert cleared.json()["tags"] == []
    assert (
        await client.put(f"{OBS}/{obs.id}/tags", json={"tags": ["bad tag!"]})
    ).status_code == 422
    assert (
        await client.put(f"{OBS}/{obs.id}/tags", json={"tags": [f"t{i}" for i in range(101)]})
    ).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.put(f"{OBS}/{missing}/tags", json={"tags": ["a"]})).status_code == 404


async def test_report_tags(client: AsyncClient) -> None:
    report = (await client.post(REPORTS, json={"title": "R", "origin": "internal"})).json()
    response = await client.put(f"{REPORTS}/{report['id']}/tags", json={"tags": ["Intel", "q4"]})
    assert response.status_code == 200, response.text
    assert response.json()["tags"] == ["intel", "q4"]
    listed = (await client.get(REPORTS)).json()["items"][0]
    assert listed["tags"] == ["intel", "q4"]
    counts = {t["name"]: t["report_count"] for t in (await client.get(TAGS)).json()}
    assert counts == {"intel": 1, "q4": 1}
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.put(f"{REPORTS}/{missing}/tags", json={"tags": ["a"]})).status_code == 404


async def test_tag_filters_match_any(client: AsyncClient, db_session: AsyncSession) -> None:
    a = await add_observable(db_session, "192.0.2.30")
    b = await add_observable(db_session, "192.0.2.31")
    await add_observable(db_session, "192.0.2.32")
    await client.put(f"{OBS}/{a.id}/tags", json={"tags": ["red-team"]})
    await client.put(f"{OBS}/{b.id}/tags", json={"tags": ["blue", "red-team"]})

    async def obs_values(query: str) -> set[str]:
        return {o["value"] for o in (await client.get(f"{OBS}?{query}")).json()["items"]}

    assert await obs_values("tag=red-team") == {"192.0.2.30", "192.0.2.31"}
    assert await obs_values("tag=BLUE") == {"192.0.2.31"}
    assert await obs_values("tag=blue&tag=red-team") == {"192.0.2.30", "192.0.2.31"}
    assert await obs_values("tag=unknown") == set()
    assert (await client.get(f"{OBS}?tag=bad%20tag%3F")).status_code == 422

    r1 = (await client.post(REPORTS, json={"title": "One", "origin": "internal"})).json()
    r2 = (await client.post(REPORTS, json={"title": "Two", "origin": "internal"})).json()
    await client.post(REPORTS, json={"title": "Three", "origin": "internal"})
    await client.put(f"{REPORTS}/{r1['id']}/tags", json={"tags": ["x"]})
    await client.put(f"{REPORTS}/{r2['id']}/tags", json={"tags": ["y"]})

    async def titles(query: str) -> set[str]:
        return {r["title"] for r in (await client.get(f"{REPORTS}?{query}")).json()["items"]}

    assert await titles("tag=x&tag=y") == {"One", "Two"}
    assert await titles("tag=y") == {"Two"}


async def test_delete_tag_removes_assignments(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    obs = await add_observable(db_session, "192.0.2.40")
    report = (await client.post(REPORTS, json={"title": "R", "origin": "internal"})).json()
    await client.put(f"{OBS}/{obs.id}/tags", json={"tags": ["temp", "keep"]})
    await client.put(f"{REPORTS}/{report['id']}/tags", json={"tags": ["temp"]})
    temp = next(t for t in (await client.get(TAGS)).json() if t["name"] == "temp")

    assert (await client.delete(f"{TAGS}/{temp['id']}")).status_code == 204
    assert (await client.get(f"{OBS}/{obs.id}")).json()["tags"] == ["keep"]
    assert (await client.get(f"{REPORTS}/{report['id']}")).json()["tags"] == []


# ── export profile tag filter ────────────────────────────────────────────


async def test_profile_tag_filter_and_409_on_referenced_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await add_observable(db_session, "192.0.2.50")
    b = await add_observable(db_session, "192.0.2.51")
    await add_observable(db_session, "192.0.2.52")
    await client.put(f"{OBS}/{a.id}/tags", json={"tags": ["edge"]})
    await client.put(f"{OBS}/{b.id}/tags", json={"tags": ["siem"]})

    response = await client.post(
        PROFILES,
        json={"name": "Tagged", "format": "text", "confidence_min": 0, "tags": ["EDGE", "siem"]},
    )
    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile["tags"] == ["edge", "siem"]

    download = await client.get(f"{PROFILES}/{profile['id']}/download")
    assert download.text == "192.0.2.50\n192.0.2.51"
    preview = (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()
    assert preview["count"] == 2

    edge = next(t for t in (await client.get(TAGS)).json() if t["name"] == "edge")
    blocked = await client.delete(f"{TAGS}/{edge['id']}")
    assert blocked.status_code == 409
    assert "Tagged" in blocked.json()["detail"]
    # Still assigned and still filtering.
    assert (await client.get(f"{OBS}/{a.id}")).json()["tags"] == ["edge"]

    updated = await client.put(f"{PROFILES}/{profile['id']}", json={"tags": ["siem"]})
    assert updated.status_code == 200 and updated.json()["tags"] == ["siem"]
    assert (await client.get(f"{PROFILES}/{profile['id']}/download")).text == "192.0.2.51"
    assert (await client.delete(f"{TAGS}/{edge['id']}")).status_code == 204

    cleared = await client.put(f"{PROFILES}/{profile['id']}", json={"tags": []})
    assert cleared.json()["tags"] == []
    assert (await client.get(f"{PROFILES}/{profile['id']}/preview")).json()["count"] == 3


async def test_profile_unknown_or_invalid_tag_422(client: AsyncClient) -> None:
    unknown = await client.post(
        PROFILES, json={"name": "U", "format": "text", "tags": ["never-created"]}
    )
    assert unknown.status_code == 422
    assert "Tag not found: never-created" in unknown.json()["detail"]
    invalid = await client.post(PROFILES, json={"name": "I", "format": "text", "tags": ["a b?"]})
    assert invalid.status_code == 422
    assert (await client.get(TAGS)).json() == []  # profiles never create tags


async def test_retention_removes_tag_assignments_but_keeps_tags(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from cti.models.tag import observable_tags
    from cti.services.retention import enforce_retention

    now = datetime.now(UTC).replace(tzinfo=None)
    old = await add_observable(db_session, "192.0.2.60", last_seen=now - timedelta(days=400))
    await client.put(f"{OBS}/{old.id}/tags", json={"tags": ["expired"]})

    assert await enforce_retention(db_session, 180, now=now) == 1
    remaining = await db_session.scalar(select(func.count()).select_from(observable_tags))
    assert remaining == 0
    assert [t["name"] for t in (await client.get(TAGS)).json()] == ["expired"]
