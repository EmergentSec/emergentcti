"""Tests for feed API response fields: has_auth and auth_supported, and auth-key endpoint."""

from __future__ import annotations

import uuid

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
# B2 — PUT /feeds/{id}/auth-key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_auth_key_returns_200_and_has_auth(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT auth-key on a preconfigured auth feed returns 200 with has_auth=True."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "my-secret-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_auth"] is True
    assert data["auth_supported"] is True
    # Never expose the encrypted blob
    assert "auth_config_encrypted" not in data


@pytest.mark.asyncio
async def test_set_auth_key_merges_into_template(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The stored auth config contains template fields plus api_key_value."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "my-secret-key"},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    assert feed.auth_config_encrypted is not None
    stored = decrypt_config(feed.auth_config_encrypted)
    # AbuseIPDB template: {"auth_type": "api_key", "api_key_header": "Key"}
    assert stored["auth_type"] == "api_key"
    assert stored["api_key_header"] == "Key"
    assert stored["api_key_value"] == "my-secret-key"


@pytest.mark.asyncio
async def test_set_auth_key_bearer_feed_sets_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """For a bearer-auth feed (urlscan.io), the stored config also contains 'token'."""
    feed = Feed(
        name="urlscan.io",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=65,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "bearer-secret"},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["auth_type"] == "bearer"
    assert stored["api_key_value"] == "bearer-secret"
    assert stored["token"] == "bearer-secret"


@pytest.mark.asyncio
async def test_set_auth_key_on_unsupported_feed_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT auth-key on a preconfigured feed with no auth support returns 400."""
    feed = Feed(
        name="CINSscore",
        feed_type=FeedType.FILE,
        is_preconfigured=True,
        default_confidence=65,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "my-secret-key"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_auth_key_on_custom_feed_returns_400(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT auth-key on a non-preconfigured feed returns 400."""
    feed = Feed(
        name="MyCustomFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "my-secret-key"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_auth_key_on_missing_feed_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT auth-key on a non-existent feed returns 404."""
    resp = await client.put(
        f"/api/v1/feeds/{uuid.uuid4()}/auth-key",
        json={"api_key": "my-secret-key"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_auth_key_overwrites_previous(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Calling auth-key twice replaces the previous stored key."""
    old_config = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "old-key"}
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
        auth_config_encrypted=encrypt_config(old_config),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}/auth-key",
        json={"api_key": "new-key"},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["api_key_value"] == "new-key"
