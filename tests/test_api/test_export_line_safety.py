"""Text exports are one indicator per line: no line-injection past the allowlist."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import ObservableType
from cti.services.observable_service import is_line_safe
from tests.policy_helpers import add_observable, allow

DOMAIN = ObservableType.DOMAIN_NAME
PROFILES = "/api/v1/export/profiles"
CACHE_KEY = "blocklist:ip-addr:70:None:None"

# Each would add a second "line" (10.0.0.5, an allowlisted address) to a text export.
INJECTIONS = [
    "203.0.113.9\n10.0.0.5",
    "203.0.113.9\r\n10.0.0.5",
    "203.0.113.9\r10.0.0.5",
    "203.0.113.9\x0b10.0.0.5",
    "203.0.113.9\x0c10.0.0.5",
    "203.0.113.9\x1e10.0.0.5",
    "203.0.113.9\x8510.0.0.5",
    "203.0.113.9\u202810.0.0.5",
    "203.0.113.9\u202910.0.0.5",
    "203.0.113.9\x0010.0.0.5",
    "203.0.113.9\t10.0.0.5",
    "\n10.0.0.5",
]


@pytest.mark.parametrize("value", INJECTIONS)
def test_is_line_safe_rejects_breaks_and_controls(value: str) -> None:
    assert not is_line_safe(value)


@pytest.mark.parametrize("value", ["203.0.113.9", "exämple.com", "cmd /c whoami", "a b", ""])
def test_is_line_safe_accepts_ordinary_values(value: str) -> None:
    assert is_line_safe(value)


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


async def _seed(client: AsyncClient, db: AsyncSession, injected: str) -> None:
    await add_observable(db, "203.0.113.1")
    await add_observable(db, injected)
    await allow(client, "exact", "10.0.0.5", "ip-addr")


async def _text_profile(client: AsyncClient, **extra: object) -> str:
    body = {"name": "P", "format": "text", "type": "ip-addr", **extra}
    response = await client.post(PROFILES, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assert_clean(text: str) -> None:
    assert text.splitlines() == ["203.0.113.1"]
    assert "10.0.0.5" not in text


@pytest.mark.parametrize("injected", INJECTIONS)
async def test_blocklist_omits_injected_values(
    client: AsyncClient, db_session: AsyncSession, injected: str
) -> None:
    await _seed(client, db_session, injected)
    response = await client.get("/api/v1/export/blocklist/ip-addr")
    _assert_clean(response.text)
    assert response.headers["X-Observable-Count"] == "1"


@pytest.mark.parametrize("injected", INJECTIONS)
async def test_text_export_omits_injected_values(
    client: AsyncClient, db_session: AsyncSession, injected: str
) -> None:
    await _seed(client, db_session, injected)
    response = await client.get("/api/v1/export/text")
    _assert_clean(response.text)
    assert response.headers["X-Observable-Count"] == "1"


@pytest.mark.parametrize("injected", INJECTIONS)
async def test_text_profile_download_and_preview_omit_injected_values(
    client: AsyncClient, db_session: AsyncSession, injected: str
) -> None:
    await _seed(client, db_session, injected)
    profile_id = await _text_profile(client)

    download = await client.get(f"{PROFILES}/{profile_id}/download")
    _assert_clean(download.text)
    assert download.headers["X-Observable-Count"] == "1"

    preview = (await client.get(f"{PROFILES}/{profile_id}/preview")).json()
    assert preview == {"count": 1, "excluded_allowlisted": 0, "sample": ["203.0.113.1"]}


async def test_injection_cannot_smuggle_other_types_either(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_observable(db_session, "evil.test\nintranet.corp.example", DOMAIN)
    await add_observable(db_session, "bad.test", DOMAIN)
    await allow(client, "domain_suffix", "corp.example")

    blocklist = await client.get("/api/v1/export/blocklist/domain-name")
    assert blocklist.text == "bad.test"
    profile_id = await _text_profile(client, type=None)
    assert (await client.get(f"{PROFILES}/{profile_id}/download")).text == "bad.test"
    assert (await client.get("/api/v1/export/text")).text == "bad.test"


async def test_json_exports_keep_literal_values(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    injected = "203.0.113.9\n10.0.0.5"
    await _seed(client, db_session, injected)

    data = (await client.get("/api/v1/export/json")).json()
    assert {o["value"] for o in data["observables"]} == {"203.0.113.1", injected}

    response = await client.post(PROFILES, json={"name": "J", "format": "json"})
    profile_id = response.json()["id"]
    download = (await client.get(f"{PROFILES}/{profile_id}/download")).json()
    assert {o["value"] for o in download["observables"]} == {"203.0.113.1", injected}
    preview = (await client.get(f"{PROFILES}/{profile_id}/preview")).json()
    assert preview["count"] == 2
    assert set(preview["sample"]) == {"203.0.113.1", injected}


# ── cache ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("injected", INJECTIONS)
async def test_cache_miss_never_stores_unsafe_values(
    client: AsyncClient, db_session: AsyncSession, fake_cache: dict[str, str], injected: str
) -> None:
    await _seed(client, db_session, injected)

    miss = await client.get("/api/v1/export/blocklist/ip-addr")
    assert miss.headers["X-Cache"] == "MISS"
    _assert_clean(miss.text)
    # Skipped before the pre-policy cache is populated.
    assert fake_cache[CACHE_KEY] == "203.0.113.1"

    hit = await client.get("/api/v1/export/blocklist/ip-addr")
    assert hit.headers["X-Cache"] == "HIT"
    _assert_clean(hit.text)
    assert hit.headers["X-Observable-Count"] == "1"


async def test_cache_hit_from_older_release_is_resanitized(
    client: AsyncClient, fake_cache: dict[str, str]
) -> None:
    # Written before line-safety existed: an embedded newline already split the
    # value, and a carriage return / separator still rides inside a "line".
    fake_cache[CACHE_KEY] = (
        "203.0.113.1\n203.0.113.9\n10.0.0.5\n203.0.113.7\r10.0.0.5\n\n203.0.113.8\u202810.0.0.5"
    )
    await allow(client, "exact", "10.0.0.5", "ip-addr")

    hit = await client.get("/api/v1/export/blocklist/ip-addr")
    assert hit.headers["X-Cache"] == "HIT"
    # Every surviving line is a whole, policy-checked value.
    assert hit.text == "203.0.113.1\n203.0.113.9"
    assert hit.headers["X-Observable-Count"] == "2"
