"""Settings → AI API contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from cti.core.dependencies import get_current_auth
from cti.models.ai import AiProvider, AiProviderConfig, AiSettingsRecord
from cti.models.user import User, UserRole

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from pytest_httpx import HTTPXMock
    from sqlalchemy.ext.asyncio import AsyncSession

BASE = "/api/v1/settings/ai"
FAKE_KEY = "sk-test-not-a-real-key-0000"


@pytest.fixture
async def ordinary_user(db_session: AsyncSession) -> User:
    user = User(
        username="ai-settings-user",
        password_hash="unused",
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def ordinary_client(
    app: FastAPI,
    ordinary_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    async def authenticate_as_user() -> User:
        return ordinary_user

    app.dependency_overrides[get_current_auth] = authenticate_as_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_current_auth, None)


async def _configure(client: AsyncClient, provider: str, key: str = FAKE_KEY) -> None:
    response = await client.put(f"{BASE}/providers/{provider}", json={"api_key": key})
    assert response.status_code == 200, response.text


async def test_every_endpoint_requires_admin(ordinary_client: AsyncClient) -> None:
    cases = [
        ("GET", BASE, None),
        ("PUT", f"{BASE}/providers/openai", {"api_key": FAKE_KEY}),
        ("DELETE", f"{BASE}/providers/openai", None),
        ("POST", f"{BASE}/providers/openai/check", None),
        ("GET", f"{BASE}/providers/openai/models", None),
        (
            "POST",
            f"{BASE}/providers/openai/inference-test",
            {"model": "gpt-test", "confirm": True},
        ),
        (
            "PUT",
            f"{BASE}/default",
            {"provider": "openai", "model": "gpt-test", "is_custom": True},
        ),
        ("DELETE", f"{BASE}/default", None),
    ]

    for method, path, body in cases:
        response = await ordinary_client.request(method, path, json=body)
        assert response.status_code == 403, (method, path, response.text)


async def test_settings_always_lists_all_providers(client: AsyncClient) -> None:
    response = await client.get(BASE)

    assert response.status_code == 200
    assert [item["provider"] for item in response.json()["providers"]] == [
        "anthropic",
        "openai",
        "openrouter",
        "xai",
    ]
    assert all(not item["configured"] for item in response.json()["providers"])
    assert response.json()["default"] is None
    assert response.json()["roles"] == {"research": None, "writer": None}


async def test_key_is_encrypted_and_save_makes_no_network_call(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": f"  {FAKE_KEY}  "},
    )

    assert response.status_code == 200
    assert response.json()["key_hint"] == "0000"
    config = await db_session.get(AiProviderConfig, AiProvider.OPENAI)
    assert config is not None
    assert config.credentials_encrypted != FAKE_KEY.encode()
    assert FAKE_KEY.encode() not in config.credentials_encrypted
    assert httpx_mock.get_requests() == []


async def test_key_length_is_validated_after_strip_and_short_keys_have_no_hint(
    client: AsyncClient,
) -> None:
    exact_limit = "k" * 512
    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": f"  {exact_limit}  "},
    )
    assert response.status_code == 200
    assert response.json()["key_hint"] == "kkkk"

    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": "short-key"},
    )
    assert response.status_code == 200
    assert response.json()["key_hint"] is None

    rejected_key = "k" * 513
    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": rejected_key},
    )
    assert response.status_code == 422
    assert rejected_key not in response.text
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}

    for rejected_key in ("", "   "):
        response = await client.put(
            f"{BASE}/providers/openai",
            json={"api_key": rejected_key},
        )
        assert response.status_code == 422
        assert "input" not in response.json()["detail"][0]
        assert "ctx" not in response.json()["detail"][0]


@pytest.mark.parametrize(
    "rejected_key",
    ["sk-test-\N{LATIN SMALL LETTER E WITH ACUTE}-secret", "sk-test-line\nbreak"],
)
async def test_non_ascii_and_control_keys_are_rejected_without_echo(
    client: AsyncClient,
    db_session: AsyncSession,
    rejected_key: str,
) -> None:
    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": rejected_key},
    )

    assert response.status_code == 422
    assert rejected_key not in response.text
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}
    assert await db_session.get(AiProviderConfig, AiProvider.OPENAI) is None


async def test_raw_key_absent_from_every_endpoint_response(
    client: AsyncClient,
    httpx_mock: HTTPXMock,
    priced_gpt_test: None,
) -> None:
    responses = []
    responses.append(
        await client.put(f"{BASE}/providers/openai", json={"api_key": FAKE_KEY})
    )
    responses.append(await client.get(BASE))

    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        json={"data": [{"id": "gpt-test"}]},
    )
    responses.append(await client.post(f"{BASE}/providers/openai/check"))

    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        json={"data": [{"id": "gpt-test"}]},
    )
    responses.append(await client.get(f"{BASE}/providers/openai/models"))
    responses.append(
        await client.put(
            f"{BASE}/default",
            json={"provider": "openai", "model": "gpt-test", "is_custom": False},
        )
    )
    responses.append(
        await client.put(
            f"{BASE}/providers/openai",
            json={"api_key": FAKE_KEY * 32},
        )
    )

    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={"choices": []},
    )
    responses.append(
        await client.post(
            f"{BASE}/providers/openai/inference-test",
            json={"model": "gpt-test", "confirm": True},
        )
    )
    responses.append(await client.delete(f"{BASE}/default"))
    responses.append(await client.delete(f"{BASE}/providers/openai"))
    responses.append(await client.post(f"{BASE}/providers/openai/check"))

    assert all(response.status_code < 500 for response in responses)
    assert any(400 <= response.status_code < 500 for response in responses)
    assert all(FAKE_KEY not in response.text for response in responses)


async def test_replace_key_invalidates_cache_and_check_state(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _configure(client, "openai")
    config = await db_session.get(AiProviderConfig, AiProvider.OPENAI)
    assert config is not None
    config.model_cache = [{"id": "old", "name": "old", "context_length": None}]
    config.models_fetched_at = datetime.now(UTC).replace(tzinfo=None)
    config.last_check_status = "error"
    config.last_check_category = "invalid_credentials"
    config.last_checked_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.flush()
    default = await client.put(
        f"{BASE}/default",
        json={"provider": "openai", "model": "old", "is_custom": False},
    )
    assert default.status_code == 200

    response = await client.put(
        f"{BASE}/providers/openai",
        json={"api_key": "sk-test-replacement-not-real-1111"},
    )

    assert response.status_code == 200
    assert config.model_cache is None
    assert config.models_fetched_at is None
    assert config.last_check_status is None
    assert config.last_check_category is None
    assert config.last_checked_at is None
    assert (await client.get(BASE)).json()["default"]["model"] == "old"


async def test_delete_provider_clears_default_without_fallback(client: AsyncClient) -> None:
    await _configure(client, "openai")
    response = await client.put(
        f"{BASE}/default",
        json={"provider": "openai", "model": "  custom/model  ", "is_custom": True},
    )
    assert response.status_code == 200

    assert (await client.delete(f"{BASE}/providers/openai")).status_code == 204
    settings = (await client.get(BASE)).json()
    assert settings["default"] is None
    assert not any(
        item["configured"] for item in settings["providers"] if item["provider"] == "openai"
    )


async def test_database_provider_delete_leaves_no_visible_default_and_repairs_on_write(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await db_session.execute(text("PRAGMA foreign_keys = ON"))
    assert await db_session.scalar(text("PRAGMA foreign_keys")) == 1
    try:
        await _configure(client, "openai")
        response = await client.put(
            f"{BASE}/default",
            json={"provider": "openai", "model": "orphaned-model", "is_custom": True},
        )
        assert response.status_code == 200

        await db_session.execute(
            text("DELETE FROM ai_providers WHERE provider = :provider"),
            {"provider": "openai"},
        )
        db_session.expire_all()

        assert (await client.get(BASE)).json()["default"] is None
        settings = await db_session.get(AiSettingsRecord, 1)
        assert settings is not None
        assert settings.default_provider is None
        assert settings.default_model == "orphaned-model"

        await _configure(client, "xai")
        assert settings.default_model is None
        assert settings.default_model_is_custom is False
    finally:
        await db_session.rollback()
        await db_session.execute(text("PRAGMA foreign_keys = OFF"))
        await db_session.commit()


async def test_delete_missing_provider_is_404(client: AsyncClient) -> None:
    response = await client.delete(f"{BASE}/providers/openai")

    assert response.status_code == 404
    assert response.json()["category"] == "not_configured"


async def test_model_cache_ttl_refresh_and_failure_are_non_destructive(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    await _configure(client, "openai")
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        json={"data": [{"id": "gpt-cached"}, {"id": "text-embedding-hidden"}]},
    )

    live = await client.get(f"{BASE}/providers/openai/models")
    cached = await client.get(f"{BASE}/providers/openai/models")

    assert live.json()["source"] == "live"
    assert [model["id"] for model in live.json()["models"]] == ["gpt-cached"]
    assert cached.json()["source"] == "cache"
    assert len(httpx_mock.get_requests()) == 1

    default = await client.put(
        f"{BASE}/default",
        json={"provider": "openai", "model": "gpt-cached", "is_custom": False},
    )
    assert default.status_code == 200
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        status_code=503,
        text="provider details that must not escape",
    )

    failed_refresh = await client.get(f"{BASE}/providers/openai/models?refresh=true")

    assert failed_refresh.status_code == 200
    assert failed_refresh.json()["source"] == "cache"
    assert failed_refresh.json()["error"]["category"] == "provider_error"
    assert "provider details" not in failed_refresh.text
    assert (await client.get(BASE)).json()["default"]["model"] == "gpt-cached"
    config = await db_session.get(AiProviderConfig, AiProvider.OPENAI)
    assert config is not None
    assert config.model_cache is not None


async def test_stale_cache_fetches_live(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    await _configure(client, "xai")
    config = await db_session.get(AiProviderConfig, AiProvider.XAI)
    assert config is not None
    config.model_cache = [{"id": "old", "name": "old", "context_length": None}]
    config.models_fetched_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
    await db_session.flush()
    httpx_mock.add_response(
        url="https://api.x.ai/v1/models",
        json={"data": [{"id": "new"}]},
    )

    response = await client.get(f"{BASE}/providers/xai/models")

    assert response.json()["source"] == "live"
    assert response.json()["models"][0]["id"] == "new"


async def test_discovery_failure_without_cache_returns_fallback(
    client: AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    await _configure(client, "anthropic")
    httpx_mock.add_response(
        url="https://api.anthropic.com/v1/models?limit=1000",
        status_code=429,
    )

    response = await client.get(f"{BASE}/providers/anthropic/models")

    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    names = [model["name"] for model in response.json()["models"]]
    assert names == sorted(names, key=str.casefold)
    assert response.json()["error"]["category"] == "rate_limited"


async def test_not_configured_operations_return_409(client: AsyncClient) -> None:
    responses = [
        await client.post(f"{BASE}/providers/openai/check"),
        await client.get(f"{BASE}/providers/openai/models"),
        await client.post(
            f"{BASE}/providers/openai/inference-test",
            json={"model": "gpt-test", "confirm": True},
        ),
        await client.put(
            f"{BASE}/default",
            json={"provider": "openai", "model": "gpt-test", "is_custom": True},
        ),
    ]

    assert all(response.status_code == 409 for response in responses)
    assert all(response.json()["category"] == "not_configured" for response in responses)


async def test_default_validation_and_exact_custom_preservation(
    client: AsyncClient,
    httpx_mock: HTTPXMock,
) -> None:
    await _configure(client, "xai")

    fallback = await client.put(
        f"{BASE}/default",
        json={"provider": "xai", "model": "grok-4", "is_custom": False},
    )
    assert fallback.status_code == 200

    unavailable = await client.put(
        f"{BASE}/default",
        json={"provider": "xai", "model": "not-listed", "is_custom": False},
    )
    assert unavailable.status_code == 422
    assert unavailable.json()["category"] == "model_unavailable"
    assert "custom ID" in unavailable.json()["message"]

    exact = "  Account/Specific Model  "
    custom = await client.put(
        f"{BASE}/default",
        json={"provider": "xai", "model": exact, "is_custom": True},
    )
    assert custom.status_code == 200
    assert custom.json()["model"] == exact
    assert (await client.get(BASE)).json()["default"]["model"] == exact
    assert httpx_mock.get_requests() == []


@pytest.mark.parametrize("model", ["", "   ", "line\nbreak", "x" * 256])
async def test_default_rejects_invalid_model_ids(client: AsyncClient, model: str) -> None:
    await _configure(client, "openrouter")

    response = await client.put(
        f"{BASE}/default",
        json={"provider": "openrouter", "model": model, "is_custom": True},
    )

    assert response.status_code == 422


async def test_clear_default_is_idempotent(client: AsyncClient) -> None:
    assert (await client.delete(f"{BASE}/default")).status_code == 204
    assert (await client.delete(f"{BASE}/default")).status_code == 204


async def test_check_persists_safe_error_category(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
) -> None:
    await _configure(client, "openrouter")
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/key",
        status_code=401,
        text="raw provider response",
    )

    response = await client.post(f"{BASE}/providers/openrouter/check")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]["category"] == "invalid_credentials"
    assert "raw provider response" not in response.text
    config = await db_session.get(AiProviderConfig, AiProvider.OPENROUTER)
    assert config is not None
    assert config.last_check_status == "error"
    assert config.last_check_category == "invalid_credentials"
    assert config.last_checked_at is not None


@pytest.mark.parametrize("confirm", [False, 1, "true", None])
async def test_inference_requires_literal_confirmation(
    client: AsyncClient,
    httpx_mock: HTTPXMock,
    confirm: object,
) -> None:
    await _configure(client, "openai")

    response = await client.post(
        f"{BASE}/providers/openai/inference-test",
        json={"model": "gpt-test", "confirm": confirm},
    )

    assert response.status_code == 422
    assert httpx_mock.get_requests() == []


async def test_confirmed_inference_uses_fixed_prompt(
    client: AsyncClient,
    httpx_mock: HTTPXMock,
    priced_gpt_test: None,
) -> None:
    await _configure(client, "openai")
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={"choices": []},
    )

    response = await client.post(
        f"{BASE}/providers/openai/inference-test",
        json={"model": "gpt-test", "confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    request = httpx_mock.get_request()
    assert request is not None
    assert b"Reply with the single word: OK" in request.content
    assert b"indicator" not in request.content


async def test_unknown_provider_is_422(client: AsyncClient) -> None:
    response = await client.put(
        f"{BASE}/providers/not-a-provider",
        json={"api_key": FAKE_KEY},
    )

    assert response.status_code == 422


async def test_settings_row_uses_singleton_id(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _configure(client, "openai")
    await client.put(
        f"{BASE}/default",
        json={"provider": "openai", "model": "custom", "is_custom": True},
    )

    rows = (await db_session.scalars(select(AiSettingsRecord))).all()
    assert [row.id for row in rows] == [1]
