"""Tests for feed API auth fields (has_auth/auth_supported) and the PUT auth-config merge."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.feeds.defaults import DEFAULT_FEEDS
from cti.models.feed import Feed, FeedType
from cti.services.feed_auth import REPAIR_MESSAGE, URL_TEMPLATE_URL_CHANGE_MESSAGE
from tests.policy_helpers import non_admin_client


def _corrupted_auth_blob(valid_config: dict) -> bytes:
    encrypted = encrypt_config(valid_config)
    tampered = bytearray(encrypted)
    tampered[len(tampered) // 2] ^= 0xFF
    return bytes(tampered)


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
    assert data["auth_needs_repair"] is True
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
async def test_partial_auth_config_on_custom_feed_with_no_base_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with partial auth_config on a custom feed with no existing auth returns 422."""
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
    assert resp.status_code == 422
    assert resp.json()["detail"] == REPAIR_MESSAGE


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


# ---------------------------------------------------------------------------
# Guard tests: empty / absent secret must never wipe existing credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_api_key_value_leaves_stored_key_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with api_key_value='' must return 200 and leave the stored key intact (no-op)."""
    original_config = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "original-secret"}
    feed = Feed(
        name="MyFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(original_config),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": ""}},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["api_key_value"] == "original-secret"


@pytest.mark.asyncio
async def test_absent_secret_in_partial_auth_config_is_noop(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with auth_config containing no secret key must return 200 and leave credentials intact."""
    original_config = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "original-secret"}
    feed = Feed(
        name="MyFeed2",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(original_config),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"foo": "bar"}},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["api_key_value"] == "original-secret"


@pytest.mark.asyncio
async def test_set_key_via_template_does_not_mutate_default_global(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Setting a key on a preconfigured feed (template path) must not write the
    secret back into the shared DEFAULT_FEEDS module global."""
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
        json={"auth_config": {"api_key_value": "leaky-secret"}},
    )
    assert resp.status_code == 200

    template = next(
        d["auth_config_template"] for d in DEFAULT_FEEDS if d["name"] == "AbuseIPDB"
    )
    assert "api_key_value" not in template
    assert "token" not in template


@pytest.mark.asyncio
async def test_preconfigured_description_can_be_edited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Description is in the preconfigured allowed set, so edits persist (no silent no-op)."""
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
        description="original",
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"description": "updated by admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated by admin"


# ---------------------------------------------------------------------------
# Issue #21 — nullable field clearing, auth repair, guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_omitting_schedule_and_description_leaves_them_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="ManualFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        description="keep me",
        schedule_cron=None,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"default_confidence": 55},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "keep me"
    assert data["schedule_cron"] is None


@pytest.mark.asyncio
async def test_explicit_null_clears_description_and_schedule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="ScheduledFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        description="will clear",
        schedule_cron="0 */6 * * *",
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"description": None, "schedule_cron": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] is None
    assert data["schedule_cron"] is None

    await db_session.refresh(feed)
    assert feed.description is None
    assert feed.schedule_cron is None


@pytest.mark.asyncio
async def test_legacy_auth_partial_rotation_returns_repair_message(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="LegacyAuthFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config({"api_key": "secret123"}),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "new-secret"}},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == REPAIR_MESSAGE


@pytest.mark.asyncio
async def test_full_auth_config_repairs_legacy_storage(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="LegacyAuthFeed2",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config({"api_key": "secret123"}),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={
            "auth_config": {
                "auth_type": "api_key",
                "api_key_header": "X-Key",
                "api_key_value": "repaired",
            }
        },
    )
    assert resp.status_code == 200
    assert resp.json()["auth_needs_repair"] is False
    assert "api_key_value" not in resp.text
    assert "repaired" not in resp.text


@pytest.mark.asyncio
async def test_url_template_partial_rotation_keeps_auth_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    old = {
        "auth_type": "url_template",
        "api_key_value": "old-template-key",
    }
    feed = Feed(
        name="TemplateFeed",
        feed_type=FeedType.API,
        url="https://example.com/fetch?key={api_key}",
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(old),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "rotated"}},
    )
    assert resp.status_code == 200

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["auth_type"] == "url_template"
    assert stored["api_key_value"] == "rotated"


@pytest.mark.asyncio
async def test_invalid_full_auth_config_on_create_returns_422(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/feeds",
        json={
            "name": "BadAuth",
            "feed_type": "api",
            "auth_config": {"auth_type": "nope", "api_key_value": "x"},
        },
    )
    assert resp.status_code == 422
    assert "not supported" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_undecryptable_auth_list_and_detail_return_repair_flag(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    valid = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "secret"}
    feed = Feed(
        name="UndecryptableFeed",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=_corrupted_auth_blob(valid),
    )
    db_session.add(feed)
    await db_session.commit()

    list_resp = await client.get("/api/v1/feeds")
    assert list_resp.status_code == 200
    row = next(item for item in list_resp.json() if item["id"] == str(feed.id))
    assert row["auth_needs_repair"] is True

    detail_resp = await client.get(f"/api/v1/feeds/{feed.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["auth_needs_repair"] is True


@pytest.mark.asyncio
async def test_undecryptable_auth_description_only_put_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    valid = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "secret"}
    feed = Feed(
        name="UndecryptableFeed2",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        description="before",
        auth_config_encrypted=_corrupted_auth_blob(valid),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"description": "after"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "after"
    assert resp.json()["auth_needs_repair"] is True


@pytest.mark.asyncio
async def test_undecryptable_auth_partial_rotation_returns_repair_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    valid = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "secret"}
    feed = Feed(
        name="UndecryptableFeed3",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=_corrupted_auth_blob(valid),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "new-secret"}},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == REPAIR_MESSAGE


@pytest.mark.asyncio
async def test_undecryptable_preconfigured_partial_rotation_uses_template(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    valid = {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "secret"}
    feed = Feed(
        name="AbuseIPDB",
        feed_type=FeedType.API,
        is_preconfigured=True,
        default_confidence=85,
        auth_config_encrypted=_corrupted_auth_blob(valid),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": "fresh-key"}},
    )
    assert resp.status_code == 200
    assert resp.json()["has_auth"] is True
    assert resp.json()["auth_needs_repair"] is False


@pytest.mark.asyncio
async def test_url_template_url_change_dropping_placeholder_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    old_url = "https://example.com/fetch?key={api_key}"
    auth = {"auth_type": "url_template", "api_key_value": "template-key"}
    feed = Feed(
        name="UrlTemplateFeed",
        feed_type=FeedType.API,
        url=old_url,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(auth),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"url": "https://example.com/fetch?key=hardcoded"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == URL_TEMPLATE_URL_CHANGE_MESSAGE

    await db_session.refresh(feed)
    assert feed.url == old_url


@pytest.mark.asyncio
async def test_url_template_url_change_with_full_auth_config_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    old_url = "https://example.com/fetch?key={api_key}"
    auth = {"auth_type": "url_template", "api_key_value": "template-key"}
    new_url = "https://other.example/data?token={api_key}"
    feed = Feed(
        name="UrlTemplateFeed2",
        feed_type=FeedType.API,
        url=old_url,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(auth),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={
            "url": new_url,
            "auth_config": {
                "auth_type": "url_template",
                "api_key_value": "rotated-key",
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["url"] == new_url
    assert resp.json()["auth_needs_repair"] is False

    await db_session.refresh(feed)
    stored = decrypt_config(feed.auth_config_encrypted)
    assert stored["api_key_value"] == "rotated-key"


@pytest.mark.asyncio
async def test_undecryptable_auth_url_change_allowed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    valid = {"auth_type": "url_template", "api_key_value": "k"}
    old_url = "https://example.com/fetch?key={api_key}"
    new_url = "https://example.com/fetch?key=hardcoded"
    feed = Feed(
        name="UndecryptableUrlFeed",
        feed_type=FeedType.API,
        url=old_url,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=_corrupted_auth_blob(valid),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"url": new_url},
    )
    assert resp.status_code == 200
    assert resp.json()["url"] == new_url
    assert resp.json()["auth_needs_repair"] is True


@pytest.mark.asyncio
async def test_numeric_partial_secret_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="NumericPartial",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
        auth_config_encrypted=encrypt_config(
            {"auth_type": "api_key", "api_key_header": "Key", "api_key_value": "old"}
        ),
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"api_key_value": 12345}},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "auth_config api_key_value must be a string"


@pytest.mark.asyncio
async def test_invalid_full_auth_config_on_update_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    feed = Feed(
        name="UpdateBadAuth",
        feed_type=FeedType.API,
        is_preconfigured=False,
        default_confidence=50,
    )
    db_session.add(feed)
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/feeds/{feed.id}",
        json={"auth_config": {"auth_type": "api_key", "api_key_header": ""}},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "auth_config api_key_header must be a non-empty string"


@pytest.mark.asyncio
async def test_non_admin_feed_update_returns_403(app) -> None:
    async with non_admin_client(app) as user:
        resp = await user.put(
            f"/api/v1/feeds/{uuid.uuid4()}",
            json={"enabled": False},
        )
        assert resp.status_code == 403
