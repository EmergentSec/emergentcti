"""Tests for feed API response fields: has_auth and auth_supported, and auth-key endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.models.feed import Feed, FeedType


@pytest.mark.asyncio
async def test_preconfigured_auth_feed_has_auth_supported(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A preconfigured feed that requires an API key → auth_supported is True."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.get(f"/api/v1/feeds/{feed.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_supported"] is True
    assert data["has_auth"] is False


@pytest.mark.asyncio
async def test_feed_with_encrypted_auth_has_auth_true(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A feed that has auth_config_encrypted set → has_auth is True."""
    feed = Feed(
        name="MyAuthFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config({"api_key": "secret123"}),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.get(f"/api/v1/feeds/{feed.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_auth"] is True
    assert data["auth_supported"] is False
    # Never expose the secret
    assert "auth_config" not in data
    assert "auth_config_encrypted" not in data


@pytest.mark.asyncio
async def test_plain_custom_feed_both_false(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A plain custom FILE feed with no auth → both has_auth and auth_supported are False."""
    feed = Feed(
        name="MyCustomFileFeed",
        feed_type=FeedType.FILE,
        is_preconfigured=False,
        default_confidence=60,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.get(f"/api/v1/feeds/{feed.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_auth"] is False
    assert data["auth_supported"] is False


@pytest.mark.asyncio
async def test_custom_feed_with_reserved_name_not_auth_supported(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A non-preconfigured feed sharing a preconfigured name → auth_supported stays False."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.get(f"/api/v1/feeds/{feed.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_supported"] is False
    assert data["has_auth"] is False


# ---------------------------------------------------------------------------
# B2 — auth_config merge via PUT /feeds/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_api_key_on_custom_feed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Partial auth_config on a custom feed with existing encrypted config rotates the key."""
    old_config = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "old"}
    feed = Feed(
        name="MyCustomFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(old_config),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "new"}},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["api_key_header"] == "Key"
    assert stored["api_key_value"] == "new"


@pytest.mark.asyncio
async def test_set_key_on_preconfigured_feed_with_no_auth(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Partial auth_config on a preconfigured feed with no existing auth uses the template."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "new-key"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_auth"] is True

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    # AbuseIPDB template: {"auth_type": "api_key", "api_key_header": "Key"}
    assert stored["auth_type"] == "api_key"
    assert stored["api_key_header"] == "Key"
    assert stored["api_key_value"] == "new-key"


@pytest.mark.asyncio
async def test_bearer_routing_sets_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """For a bearer-auth feed (urlscan.io), api_key_value is also mirrored into 'token'."""
    feed = Feed(
        name="urlscan.io",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=65,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "bearer-secret"}},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["auth_type"] == "bearer"
    assert stored["api_key_value"] == "bearer-secret"
    assert stored["token"] == "bearer-secret"


@pytest.mark.asyncio
async def test_full_replace_when_auth_type_present(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """When auth_type is supplied in auth_config, the stored config is fully replaced."""
    feed = Feed(
        name="MyFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    new_auth = {"auth_type": "api_key", "api_key_header": "X-Api", "api_key_value": "z"}
    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": new_auth},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored == new_auth


@pytest.mark.asyncio
async def test_partial_auth_config_on_custom_feed_with_no_base_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with partial auth_config on a custom feed with no existing auth returns 400."""
    feed = Feed(
        name="MyCustomFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "x"}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_normal_field_returns_200_with_correct_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT on a normal field returns 200 and the response reflects the new value.

    Regression for the MissingGreenlet bug: without db.refresh(feed) after
    commit, accessing server-generated columns (e.g. updated_at) would raise
    MissingGreenlet in a real async PostgreSQL session.
    """
    feed = Feed(
        name="MyFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"default_confidence": 42},
    )
    assert resp.status_code == 200
    assert resp.json()["default_confidence"] == 42


@pytest.mark.asyncio
async def test_preconfigured_name_field_not_updated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with 'name' on a preconfigured feed does not change the name."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"name": "Hacked"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "AbuseIPDB"
