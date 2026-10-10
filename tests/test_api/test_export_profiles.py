"""Saved export profiles: CRUD, guards, preview/download, feed deletion safety."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.export_profile import ExportProfile
from cti.models.feed import Feed
from cti.models.observable import ObservableType
from cti.services import export_profile_service, feed_service
from tests.policy_helpers import add_feed, add_observable, allow, non_admin_client

BASE = "/api/v1/export/profiles"
DOMAIN = ObservableType.DOMAIN_NAME


async def create_profile(client: AsyncClient, **overrides: object) -> dict:
    body: dict = {"name": "Perimeter IPs", "format": "text", "type": "ip-addr"}
    body.update(overrides)
    response = await client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# ── CRUD ─────────────────────────────────────────────────────────────────


async def test_list_empty(client: AsyncClient) -> None:
    response = await client.get(BASE)
    assert response.status_code == 200
    assert response.json() == []


async def test_create_applies_defaults(client: AsyncClient) -> None:
    created = await create_profile(client, name="  Minimal  ", format="json", type=None)
    assert uuid.UUID(created["id"])
    assert created["name"] == "Minimal"
    assert created["description"] is None
    assert created["format"] == "json"
    assert created["type"] is None
    assert created["confidence_min"] == 70
    assert created["max_age_days"] is None
    assert created["feed_id"] is None
    assert created["created_at"] and created["updated_at"]


async def test_create_full_and_list_and_get(client: AsyncClient, db_session: AsyncSession) -> None:
    feed = await add_feed(db_session)
    created = await create_profile(
        client,
        name="Zeta",
        description="for the edge firewall",
        confidence_min=85,
        max_age_days=30,
        feed_id=str(feed.id),
    )
    assert created["description"] == "for the edge firewall"
    assert created["confidence_min"] == 85
    assert created["max_age_days"] == 30
    assert created["feed_id"] == str(feed.id)

    await create_profile(client, name="Alpha")
    assert [p["name"] for p in (await client.get(BASE)).json()] == ["Alpha", "Zeta"]

    fetched = await client.get(f"{BASE}/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"description": "x" * 501},
        {"format": "csv"},
        {"type": "hostname"},
        {"confidence_min": -1},
        {"confidence_min": 101},
        {"max_age_days": 0},
        {"max_age_days": 36501},
        {"max_age_days": 1_000_000_000},
        {"feed_id": "not-a-uuid"},
    ],
)
async def test_create_rejects_invalid(client: AsyncClient, overrides: dict) -> None:
    body = {"name": "P", "format": "text", "type": "ip-addr", **overrides}
    response = await client.post(BASE, json=body)
    assert response.status_code == 422, response.text
    assert (await client.get(BASE)).json() == []


async def test_create_requires_name_and_format(client: AsyncClient) -> None:
    assert (await client.post(BASE, json={"format": "text"})).status_code == 422
    assert (await client.post(BASE, json={"name": "P"})).status_code == 422


async def test_create_rejects_unknown_feed(client: AsyncClient) -> None:
    response = await client.post(
        BASE, json={"name": "P", "format": "text", "feed_id": str(uuid.uuid4())}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Feed not found"


async def test_duplicate_name_conflicts(client: AsyncClient) -> None:
    await create_profile(client, name="Edge")
    response = await client.post(BASE, json={"name": " Edge ", "format": "json"})
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)

    other = await create_profile(client, name="Core")
    response = await client.put(f"{BASE}/{other['id']}", json={"name": "Edge"})
    assert response.status_code == 409
    assert len((await client.get(BASE)).json()) == 2


async def test_update_full_replace(client: AsyncClient, db_session: AsyncSession) -> None:
    feed = await add_feed(db_session)
    created = await create_profile(
        client, description="old", max_age_days=7, feed_id=str(feed.id), confidence_min=90
    )
    body = {
        "name": "Renamed",
        "description": None,
        "format": "json",
        "type": None,
        "confidence_min": 10,
        "max_age_days": None,
        "feed_id": None,
    }
    response = await client.put(f"{BASE}/{created['id']}", json=body)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert {k: updated[k] for k in body} == body
    assert updated["id"] == created["id"]
    assert (await client.get(f"{BASE}/{created['id']}")).json() == updated


async def test_update_keeps_own_name_and_omitted_fields(client: AsyncClient) -> None:
    created = await create_profile(client, confidence_min=55, max_age_days=14)
    response = await client.put(
        f"{BASE}/{created['id']}", json={"name": created["name"], "description": "now described"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["description"] == "now described"
    assert updated["confidence_min"] == 55
    assert updated["max_age_days"] == 14
    assert updated["type"] == "ip-addr"


@pytest.mark.parametrize(
    "body",
    [
        {"name": None},
        {"name": "  "},
        {"format": None},
        {"confidence_min": None},
        {"confidence_min": 500},
        {"max_age_days": 0},
        {"max_age_days": 1_000_000_000},
        {"feed_id": str(uuid.uuid4())},
    ],
)
async def test_update_rejects_invalid(client: AsyncClient, body: dict) -> None:
    created = await create_profile(client)
    response = await client.put(f"{BASE}/{created['id']}", json=body)
    assert response.status_code == 422, response.text
    assert (await client.get(f"{BASE}/{created['id']}")).json() == created


async def test_delete(client: AsyncClient) -> None:
    created = await create_profile(client)
    assert (await client.delete(f"{BASE}/{created['id']}")).status_code == 204
    assert (await client.get(BASE)).json() == []
    for method in (client.delete, client.get):
        assert (await method(f"{BASE}/{created['id']}")).status_code == 404


async def test_unknown_profile_is_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await client.put(f"{BASE}/{missing}", json={"name": "x"})).status_code == 404
    assert (await client.get(f"{BASE}/{missing}/preview")).status_code == 404
    assert (await client.get(f"{BASE}/{missing}/download")).status_code == 404


# ── auth ─────────────────────────────────────────────────────────────────


async def test_requires_authentication(client: AsyncClient, app: FastAPI) -> None:
    created = await create_profile(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        assert (await anon.get(BASE)).status_code == 401
        assert (await anon.get(f"{BASE}/{created['id']}/download")).status_code == 401
        assert (await anon.get(f"{BASE}/{created['id']}/preview")).status_code == 401
        assert (await anon.post(BASE, json={"name": "x", "format": "text"})).status_code == 401
        # Profile IDs are not credentials: no query-string token path.
        response = await anon.get(f"{BASE}/{created['id']}/download?api_key=whatever")
        assert response.status_code == 401


async def test_non_admin_reads_previews_downloads_but_cannot_mutate(
    client: AsyncClient, app: FastAPI, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "203.0.113.5")
    created = await create_profile(client)

    async with non_admin_client(app) as user:
        assert [p["id"] for p in (await user.get(BASE)).json()] == [created["id"]]
        assert (await user.get(f"{BASE}/{created['id']}/preview")).json()["count"] == 1
        download = await user.get(f"{BASE}/{created['id']}/download")
        assert download.status_code == 200
        assert download.text == "203.0.113.5"

        assert (await user.post(BASE, json={"name": "x", "format": "text"})).status_code == 403
        response = await user.put(f"{BASE}/{created['id']}", json={"name": "y"})
        assert response.status_code == 403
        assert (await user.delete(f"{BASE}/{created['id']}")).status_code == 403

    assert (await client.get(f"{BASE}/{created['id']}")).json() == created


async def test_download_works_with_api_key_header(
    app: FastAPI, client: AsyncClient, seeded_api_key: str, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "203.0.113.5")
    created = await create_profile(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as fw:
        response = await fw.get(
            f"{BASE}/{created['id']}/download", headers={"X-API-Key": seeded_api_key}
        )
    assert response.status_code == 200
    assert response.text == "203.0.113.5"


# ── download / preview ───────────────────────────────────────────────────


async def _seed_mixed(db: AsyncSession) -> Feed:
    now = datetime.now(UTC)
    feed = await add_feed(db)
    await add_observable(db, "203.0.113.9", confidence=90, feed=feed)
    await add_observable(db, "203.0.113.1", confidence=90, feed=feed)
    await add_observable(db, "198.51.100.7", confidence=90)  # other source
    await add_observable(db, "203.0.113.50", confidence=40, feed=feed)  # low confidence
    await add_observable(
        db, "203.0.113.77", confidence=90, feed=feed, last_seen=now - timedelta(days=60)
    )  # stale
    await add_observable(db, "evil.example.net", DOMAIN, confidence=90, feed=feed)
    await add_observable(db, "10.0.0.5", confidence=90, feed=feed)  # to be allowlisted
    return feed


async def test_text_download_applies_saved_filters_and_policy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await _seed_mixed(db_session)
    await allow(client, "cidr", "10.0.0.0/8")
    profile = await create_profile(
        client, name="Edge FW", confidence_min=70, max_age_days=30, feed_id=str(feed.id)
    )

    response = await client.get(f"{BASE}/{profile['id']}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "203.0.113.1\n203.0.113.9"  # alphabetical, like the blocklist
    assert response.headers["X-Observable-Count"] == "2"
    assert response.headers["Content-Disposition"] == 'attachment; filename="Edge-FW.txt"'

    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview == {
        "count": 2,
        "excluded_allowlisted": 1,
        "sample": ["203.0.113.1", "203.0.113.9"],
    }


async def test_text_profile_without_type_mixes_types(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_mixed(db_session)
    profile = await create_profile(client, type=None, confidence_min=0)
    lines = (await client.get(f"{BASE}/{profile['id']}/download")).text.split("\n")
    assert "evil.example.net" in lines
    assert "203.0.113.50" in lines
    assert len(lines) == 7
    assert lines == sorted(lines)


async def test_json_download_uses_export_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await _seed_mixed(db_session)
    await allow(client, "cidr", "10.0.0.0/8")
    profile = await create_profile(
        client, name="SIEM", format="json", max_age_days=30, feed_id=str(feed.id)
    )

    response = await client.get(f"{BASE}/{profile['id']}/download")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"exported_at", "count", "filters", "observables"}
    assert data["count"] == 2
    assert {o["value"] for o in data["observables"]} == {"203.0.113.1", "203.0.113.9"}
    assert set(data["observables"][0]) == {
        "type", "value", "confidence_score", "last_seen", "sources",
    }
    assert data["observables"][0]["sources"] == ["Feed A"]
    assert data["filters"] == {
        "profile": "SIEM",
        "type": "ip-addr",
        "confidence_min": 70,
        "max_age_days": 30,
        "feed_id": str(feed.id),
    }


async def test_json_download_returns_all_eligible_rows(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.services import observable_service

    # Tiny batches so the export spans many fetches: nothing may be dropped at a boundary.
    monkeypatch.setattr(observable_service, "_EXPORT_PAGE_SIZE", 3)
    monkeypatch.setattr(observable_service, "_BATCH_SIZE", 4)
    now = datetime.now(UTC)
    for i in range(3):
        await add_observable(db_session, f"10.0.0.{i}", last_seen=now - timedelta(minutes=i))
    for i in range(14):
        await add_observable(
            db_session, f"203.0.113.{i}", last_seen=now - timedelta(hours=1, minutes=i)
        )
    await allow(client, "cidr", "10.0.0.0/8")
    profile = await create_profile(client, format="json")
    expected = [f"203.0.113.{i}" for i in range(14)]  # newest first

    data = (await client.get(f"{BASE}/{profile['id']}/download")).json()
    assert data["count"] == 14
    assert [o["value"] for o in data["observables"]] == expected

    # No cap, advertised or otherwise: a stray ``limit`` cannot shorten a profile export.
    capped = (await client.get(f"{BASE}/{profile['id']}/download?limit=2")).json()
    assert capped["count"] == 14

    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview["count"] == data["count"]
    assert preview["excluded_allowlisted"] == 3
    assert preview["sample"] == expected


async def test_text_download_is_never_truncated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    for i in range(30):
        await add_observable(db_session, f"203.0.113.{i}")
    profile = await create_profile(client)

    # A text blocklist is always complete; a stray ``limit`` is ignored.
    response = await client.get(f"{BASE}/{profile['id']}/download?limit=5")
    assert len(response.text.split("\n")) == 30
    assert response.headers["X-Observable-Count"] == "30"

    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview["count"] == 30
    assert len(preview["sample"]) == 20


async def test_preview_excluded_counts_only_rows_matching_other_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.0.0.1", confidence=90)
    await add_observable(db_session, "10.0.0.2", confidence=20)  # filtered by confidence anyway
    await add_observable(db_session, "allowed.example.com", DOMAIN, confidence=90)  # other type
    await add_observable(db_session, "203.0.113.5", confidence=90)
    await allow(client, "cidr", "10.0.0.0/8")
    await allow(client, "domain_suffix", "example.com")
    profile = await create_profile(client)

    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview == {"count": 1, "excluded_allowlisted": 1, "sample": ["203.0.113.5"]}


async def test_empty_profile_result(client: AsyncClient) -> None:
    profile = await create_profile(client)
    response = await client.get(f"{BASE}/{profile['id']}/download")
    assert response.text == ""
    assert response.headers["X-Observable-Count"] == "0"
    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview == {"count": 0, "excluded_allowlisted": 0, "sample": []}


async def test_profile_reflects_current_data_and_policy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "10.0.0.5")
    profile = await create_profile(client)
    url = f"{BASE}/{profile['id']}/download"

    assert (await client.get(url)).text == "10.0.0.5"

    await add_observable(db_session, "203.0.113.5")
    assert (await client.get(url)).text == "10.0.0.5\n203.0.113.5"

    entry = await allow(client, "exact", "10.0.0.5", "ip-addr")
    assert (await client.get(url)).text == "203.0.113.5"

    await client.delete(f"/api/v1/allowlist/{entry['id']}")
    assert (await client.get(url)).text == "10.0.0.5\n203.0.113.5"

    await client.put(f"{BASE}/{profile['id']}", json={"confidence_min": 100})
    assert (await client.get(url)).text == ""


async def test_profile_download_ignores_blocklist_cache(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cti.api.v1 import export

    async def poisoned(key: str) -> str:
        return "10.66.66.66"

    monkeypatch.setattr(export, "cache_get", poisoned)
    await add_observable(db_session, "203.0.113.5")
    profile = await create_profile(client, confidence_min=70)
    assert (await client.get(f"{BASE}/{profile['id']}/download")).text == "203.0.113.5"


# ── feed deletion safety ─────────────────────────────────────────────────


async def test_referenced_feed_cannot_be_deleted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, name="Custom feed")
    other = await add_feed(db_session, name="Other feed")
    await add_observable(db_session, "203.0.113.5", feed=feed)
    await add_observable(db_session, "198.51.100.7", feed=other)
    profile = await create_profile(client, name="Edge", feed_id=str(feed.id))

    response = await client.delete(f"/api/v1/feeds/{feed.id}")
    assert response.status_code == 409
    assert "Edge" in response.json()["detail"]

    # Nothing changed: the feed, the reference and the scoped export all survive.
    assert (await client.get(f"/api/v1/feeds/{feed.id}")).status_code == 200
    assert (await client.get(f"{BASE}/{profile['id']}")).json()["feed_id"] == str(feed.id)
    assert (await client.get(f"{BASE}/{profile['id']}/download")).text == "203.0.113.5"


async def test_feed_deletable_once_unreferenced(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = await add_feed(db_session, name="Custom feed")
    first = await create_profile(client, name="One", feed_id=str(feed.id))
    second = await create_profile(client, name="Two", feed_id=str(feed.id))

    with pytest.raises(feed_service.FeedInUseError) as excinfo:
        await feed_service.delete_feed(db_session, feed)
    assert excinfo.value.profile_names == ["One", "Two"]

    # Either repointing or deleting the profile releases the feed.
    assert (await client.put(f"{BASE}/{first['id']}", json={"feed_id": None})).status_code == 200
    assert (await client.delete(f"{BASE}/{second['id']}")).status_code == 204

    assert await feed_service.delete_feed(db_session, feed) is True
    await db_session.commit()
    assert await feed_service.get_feed(db_session, feed.id) is None


async def test_dangling_feed_reference_fails_closed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """If a referenced feed vanishes anyway, the profile exports nothing — never everything."""
    await add_observable(db_session, "203.0.113.5")
    profile = await create_profile(client)

    row = await db_session.get(ExportProfile, uuid.UUID(profile["id"]))
    assert row is not None
    row.feed_id = uuid.uuid4()  # SQLite does not enforce the FK, simulating a lost feed
    await db_session.commit()

    assert (await client.get(f"{BASE}/{profile['id']}/download")).text == ""
    preview = (await client.get(f"{BASE}/{profile['id']}/preview")).json()
    assert preview == {"count": 0, "excluded_allowlisted": 0, "sample": []}


async def test_deprecated_preconfigured_feed_kept_while_referenced(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    referenced = await add_feed(db_session, name="Retired A", is_preconfigured=True, enabled=False)
    unreferenced = await add_feed(
        db_session, name="Retired B", is_preconfigured=True, enabled=False
    )
    await create_profile(client, feed_id=str(referenced.id))

    await feed_service.update_preconfigured_feeds(db_session)
    await db_session.commit()

    assert await feed_service.get_feed(db_session, unreferenced.id) is None
    kept = await feed_service.get_feed(db_session, referenced.id)
    assert kept is not None
    assert kept.is_preconfigured is False


# ── integrity-error classification and races ─────────────────────────────


class _PgError(Exception):
    def __init__(self, sqlstate: str, message: str) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def _integrity_error(orig: Exception) -> IntegrityError:
    return IntegrityError("stmt", {}, orig)


FK_ERRORS = [
    Exception("FOREIGN KEY constraint failed"),  # SQLite
    _PgError("23503", "insert or update on table violates constraint fk_export_profiles_feed_id"),
]
UNIQUE_ERRORS = [
    Exception("UNIQUE constraint failed: export_profiles.name"),
    _PgError("23505", "duplicate key value violates unique constraint"),
]


def _failing_flush(monkeypatch: pytest.MonkeyPatch, db: AsyncSession, orig: Exception) -> None:
    async def flush(*_args: object, **_kwargs: object) -> None:
        raise _integrity_error(orig)

    monkeypatch.setattr(db, "flush", flush)


@pytest.mark.parametrize("orig", FK_ERRORS)
def test_fk_violations_are_recognised(orig: Exception) -> None:
    assert export_profile_service.is_foreign_key_violation(_integrity_error(orig))


@pytest.mark.parametrize("orig", UNIQUE_ERRORS)
def test_unique_violations_are_not_fk_violations(orig: Exception) -> None:
    assert not export_profile_service.is_foreign_key_violation(_integrity_error(orig))


@pytest.mark.parametrize("orig", FK_ERRORS)
async def test_create_race_with_feed_deletion_reports_missing_feed(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    orig: Exception,
) -> None:
    feed = await add_feed(db_session)
    feed_id = str(feed.id)
    _failing_flush(monkeypatch, db_session, orig)  # feed deleted after the existence check

    response = await client.post(BASE, json={"name": "P", "format": "text", "feed_id": feed_id})
    assert response.status_code == 422
    assert response.json()["detail"] == "Feed not found"

    monkeypatch.undo()
    assert (await client.get(BASE)).json() == []


@pytest.mark.parametrize("orig", FK_ERRORS)
async def test_update_race_with_feed_deletion_reports_missing_feed(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    orig: Exception,
) -> None:
    feed = await add_feed(db_session)
    feed_id = str(feed.id)
    created = await create_profile(client)
    _failing_flush(monkeypatch, db_session, orig)

    response = await client.put(f"{BASE}/{created['id']}", json={"feed_id": feed_id})
    assert response.status_code == 422
    assert response.json()["detail"] == "Feed not found"

    monkeypatch.undo()
    assert (await client.get(f"{BASE}/{created['id']}")).json()["feed_id"] is None


@pytest.mark.parametrize("orig", UNIQUE_ERRORS)
async def test_create_race_on_name_still_reports_duplicate(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    orig: Exception,
) -> None:
    _failing_flush(monkeypatch, db_session, orig)
    response = await client.post(BASE, json={"name": "P", "format": "text"})
    assert response.status_code == 409
    assert "name" in response.json()["detail"]


@pytest.mark.parametrize("orig", FK_ERRORS)
async def test_feed_delete_race_with_new_profile_is_409(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    orig: Exception,
) -> None:
    """A profile starts referencing the feed after the guard's check: RESTRICT fires."""
    feed = await add_feed(db_session, name="Custom feed")
    feed_id = feed.id
    await add_observable(db_session, "203.0.113.5", feed=feed)

    real_names = feed_service._referencing_profile_names
    calls = 0

    async def names(db: AsyncSession, fid: uuid.UUID) -> list[str]:
        nonlocal calls
        calls += 1
        # First call is the pre-delete guard, which saw no reference yet.
        return [] if calls == 1 else ["Late profile"]

    monkeypatch.setattr(feed_service, "_referencing_profile_names", names)
    _failing_flush(monkeypatch, db_session, orig)

    response = await client.delete(f"/api/v1/feeds/{feed_id}")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "Late profile" in detail
    assert "export profile" in detail

    monkeypatch.undo()
    assert real_names is feed_service._referencing_profile_names
    # Fail closed: the feed and its data are untouched.
    assert (await client.get(f"/api/v1/feeds/{feed_id}")).status_code == 200
    blocklist = await client.get(f"/api/v1/export/blocklist/ip-addr?feed_id={feed_id}")
    assert blocklist.text == "203.0.113.5"


async def test_feed_delete_race_without_resolvable_names_still_409(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = await add_feed(db_session, name="Custom feed")
    feed_id = feed.id
    _failing_flush(monkeypatch, db_session, FK_ERRORS[0])

    response = await client.delete(f"/api/v1/feeds/{feed_id}")
    assert response.status_code == 409
    assert "an export profile" in response.json()["detail"]

    monkeypatch.undo()
    assert (await client.get(f"/api/v1/feeds/{feed_id}")).status_code == 200
