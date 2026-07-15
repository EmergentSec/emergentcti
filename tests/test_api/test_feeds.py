"""Tests for feed API response fields: has_auth and auth_supported."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import encrypt_config
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
