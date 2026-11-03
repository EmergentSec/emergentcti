"""Audit events for Settings → AI (issue #16, task T4)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from cti.models.audit import AuditEvent
from cti.schemas.ai import AiError, AiErrorCategory, AiModel
from cti.services import ai_settings_service, audit
from cti.services.ai.base import AiAdapterError
from tests.policy_helpers import non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from pytest_httpx import HTTPXMock
    from sqlalchemy.ext.asyncio import AsyncSession

BASE = "/api/v1/settings/ai"
FAKE_KEY = "sk-test-not-a-real-key-audit-0000"
SENTINEL = "PROVIDER-SENTINEL-c0ffee"


async def events(db: AsyncSession, action: str | None = None) -> list[AuditEvent]:
    db.expunge_all()
    query = select(AuditEvent).order_by(AuditEvent.occurred_at, AuditEvent.id)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    return list((await db.scalars(query)).all())


async def rows_json(db: AsyncSession) -> str:
    rows = (await db.execute(select(AuditEvent.__table__))).all()
    return json.dumps([list(row) for row in rows], default=str)


def assert_not_succeeded(found: list[AuditEvent]) -> None:
    assert found, "expected a failed/denied event"
    assert all(e.outcome != "succeeded" for e in found)


async def configure(client: AsyncClient, provider: str = "openai") -> None:
    response = await client.put(f"{BASE}/providers/{provider}", json={"api_key": FAKE_KEY})
    assert response.status_code == 200, response.text


class BrokenAuditSession:
    """An independent audit session whose commit always fails."""

    def add(self, _obj: object) -> None: ...

    async def commit(self) -> None:
        raise RuntimeError("audit table unavailable")

    async def __aenter__(self) -> BrokenAuditSession:
        return self

    async def __aexit__(self, *exc: object) -> None: ...


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace every provider adapter with a mock that never leaves the process."""
    fake = MagicMock()
    fake.check = AsyncMock(return_value=None)
    fake.list_models = AsyncMock(return_value=[AiModel(id="gpt-live", name="GPT live")])
    fake.inference_test = AsyncMock(return_value=None)
    monkeypatch.setattr(ai_settings_service, "get_adapter", lambda _provider: fake)
    return fake


def provider_error(category: AiErrorCategory) -> AiAdapterError:
    # The message stands in for anything provider-derived; it must never be stored.
    return AiAdapterError(AiError(category=category, message=f"upstream said {SENTINEL}"))


# ── provider keys ──────────────────────────────────────────────────────────


async def test_key_save_records_provider_only(client: AsyncClient, db_session) -> None:
    await configure(client)
    [event] = await events(db_session, "ai_provider.key_save")
    assert (event.outcome, event.resource_type, event.resource_id, event.summary) == (
        "succeeded",
        "ai_provider",
        "openai",
        {"provider": "openai"},
    )
    dumped = await rows_json(db_session)
    assert FAKE_KEY not in dumped
    assert FAKE_KEY[-4:] not in dumped  # not even the key hint


async def test_key_save_by_non_admin_is_denied(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    async with non_admin_client(app) as user:
        response = await user.put(f"{BASE}/providers/openai", json={"api_key": FAKE_KEY})
    assert response.status_code == 403
    found = await events(db_session, "ai_provider.key_save")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_id) for e in found] == [("denied", "openai")]
    assert FAKE_KEY not in await rows_json(db_session)


async def test_provider_delete_records_event(client: AsyncClient, db_session) -> None:
    await configure(client)
    assert (await client.delete(f"{BASE}/providers/openai")).status_code == 204
    [event] = await events(db_session, "ai_provider.delete")
    assert (event.outcome, event.resource_id, event.summary) == (
        "succeeded",
        "openai",
        {"provider": "openai"},
    )


async def test_provider_delete_unconfigured_records_failed(client: AsyncClient, db_session) -> None:
    assert (await client.delete(f"{BASE}/providers/openai")).status_code == 404
    found = await events(db_session, "ai_provider.delete")
    assert_not_succeeded(found)
    assert found[0].summary == {
        "provider": "openai",
        "error_code": "not_configured",
        "status": 404,
    }


# ── default model ──────────────────────────────────────────────────────────


async def test_default_set_and_clear_record_before_after(client: AsyncClient, db_session) -> None:
    await configure(client)
    body = {"provider": "openai", "model": "custom-a", "is_custom": True}
    assert (await client.put(f"{BASE}/default", json=body)).status_code == 200
    body = {"provider": "openai", "model": "custom-b", "is_custom": True}
    assert (await client.put(f"{BASE}/default", json=body)).status_code == 200
    assert (await client.delete(f"{BASE}/default")).status_code == 204

    first, second = await events(db_session, "ai_default.set")
    assert first.summary == {
        "before": {"provider": None, "model": None},
        "after": {"provider": "openai", "model": "custom-a"},
        "is_custom": True,
    }
    assert second.summary["before"] == {"provider": "openai", "model": "custom-a"}
    assert second.summary["after"] == {"provider": "openai", "model": "custom-b"}
    [cleared] = await events(db_session, "ai_default.clear")
    assert (cleared.outcome, cleared.resource_type, cleared.summary) == (
        "succeeded",
        "ai_default",
        {
            "before": {"provider": "openai", "model": "custom-b"},
            "after": {"provider": None, "model": None},
        },
    )


async def test_default_set_failure_records_failed(client: AsyncClient, db_session) -> None:
    body = {"provider": "openai", "model": "gpt-x", "is_custom": True}
    assert (await client.put(f"{BASE}/default", json=body)).status_code == 409  # not configured
    await configure(client)
    body = {"provider": "openai", "model": "not-listed", "is_custom": False}
    assert (await client.put(f"{BASE}/default", json=body)).status_code == 422
    found = await events(db_session, "ai_default.set")
    assert_not_succeeded(found)
    assert [(e.outcome, e.summary["error_code"], e.summary["status"]) for e in found] == [
        ("failed", "not_configured", 409),
        ("failed", "model_unavailable", 422),
    ]


async def test_default_clear_by_non_admin_is_denied(
    app: FastAPI, client: AsyncClient, db_session
) -> None:
    async with non_admin_client(app) as user:
        assert (await user.delete(f"{BASE}/default")).status_code == 403
    found = await events(db_session, "ai_default.clear")
    assert_not_succeeded(found)
    assert found[0].outcome == "denied"


# ── outbound AI requests ───────────────────────────────────────────────────


async def test_check_records_initiated_then_succeeded(
    client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    await configure(client)
    response = await client.post(f"{BASE}/providers/openai/check")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    adapter.check.assert_awaited_once()
    initiated, outcome = await events(db_session, "ai.request")
    meta = {"operation": "check", "provider": "openai", "model": None}
    assert (initiated.outcome, initiated.resource_id, initiated.summary) == (
        "initiated",
        "openai",
        meta,
    )
    assert (outcome.outcome, outcome.summary) == (
        "succeeded",
        {**meta, "error_code": None, "initiated_event_id": str(initiated.id)},
    )


async def test_check_provider_error_records_failed_without_message(
    client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    await configure(client)
    adapter.check.side_effect = provider_error(AiErrorCategory.INVALID_CREDENTIALS)
    response = await client.post(f"{BASE}/providers/openai/check")
    assert response.status_code == 200
    assert response.json()["ok"] is False
    found = await events(db_session, "ai.request")
    assert_not_succeeded(found)
    assert [(e.outcome, e.summary.get("error_code")) for e in found] == [
        ("initiated", None),
        ("failed", "invalid_credentials"),
    ]
    dumped = await rows_json(db_session)
    assert SENTINEL not in dumped
    assert FAKE_KEY not in dumped


async def test_unconfigured_provider_records_failed_without_contacting_it(
    client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    response = await client.post(f"{BASE}/providers/openai/check")
    assert response.status_code == 409
    adapter.check.assert_not_awaited()
    found = await events(db_session, "ai.request")
    assert [(e.outcome, e.summary) for e in found] == [
        (
            "failed",
            {
                "operation": "check",
                "provider": "openai",
                "model": None,
                "error_code": "not_configured",
                "status": 409,
            },
        )
    ]


async def test_ai_request_by_non_admin_is_denied(
    app: FastAPI, client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    async with non_admin_client(app) as user:
        assert (await user.post(f"{BASE}/providers/openai/check")).status_code == 403
    adapter.check.assert_not_awaited()
    found = await events(db_session, "ai.request")
    assert_not_succeeded(found)
    assert [(e.outcome, e.resource_id) for e in found] == [("denied", "openai")]


@pytest.mark.parametrize(
    ("method", "suffix", "body", "adapter_method"),
    [
        ("POST", "/check", None, "check"),
        ("GET", "/models?refresh=true", None, "list_models"),
        ("POST", "/inference-test", {"model": "gpt-test", "confirm": True}, "inference_test"),
    ],
)
async def test_initiated_write_failure_returns_503_and_skips_provider(
    client: AsyncClient,
    db_session,
    adapter: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    suffix: str,
    body: dict | None,
    adapter_method: str,
    priced_gpt_test: None,
) -> None:
    await configure(client)
    monkeypatch.setattr(audit, "_session_factory", BrokenAuditSession)
    response = await client.request(method, f"{BASE}/providers/openai{suffix}", json=body)
    assert response.status_code == 503
    assert response.json() == {"detail": "Audit log unavailable"}
    getattr(adapter, adapter_method).assert_not_awaited()
    assert await events(db_session, "ai.request") == []


async def test_cached_model_listing_records_no_ai_request(
    client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    await configure(client)
    live = await client.get(f"{BASE}/providers/openai/models")
    assert live.json()["source"] == "live"
    cached = await client.get(f"{BASE}/providers/openai/models")
    assert cached.json()["source"] == "cache"
    assert adapter.list_models.await_count == 1
    found = await events(db_session, "ai.request")
    assert [(e.outcome, e.summary["operation"]) for e in found] == [
        ("initiated", "list_models"),
        ("succeeded", "list_models"),
    ]


async def test_model_listing_provider_error_records_failed(
    client: AsyncClient, db_session, adapter: MagicMock
) -> None:
    await configure(client)
    adapter.list_models.side_effect = provider_error(AiErrorCategory.RATE_LIMITED)
    response = await client.get(f"{BASE}/providers/openai/models")
    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    found = await events(db_session, "ai.request")
    assert_not_succeeded(found)
    assert found[-1].summary["error_code"] == "rate_limited"
    assert SENTINEL not in await rows_json(db_session)


async def test_inference_test_never_stores_prompt_or_output(
    client: AsyncClient,
    db_session,
    httpx_mock: HTTPXMock,
    priced_gpt_test: None,
) -> None:
    await configure(client)
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={"choices": [{"message": {"role": "assistant", "content": SENTINEL}}]},
    )
    response = await client.post(
        f"{BASE}/providers/openai/inference-test", json={"model": "gpt-test", "confirm": True}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    [request] = httpx_mock.get_requests()
    prompt = json.loads(request.content)["messages"]
    initiated, outcome = await events(db_session, "ai.request")
    meta = {"operation": "inference_test", "provider": "openai", "model": "gpt-test"}
    assert initiated.summary == meta
    assert (outcome.outcome, outcome.summary) == (
        "succeeded",
        {**meta, "error_code": None, "initiated_event_id": str(initiated.id)},
    )
    dumped = await rows_json(db_session)
    assert SENTINEL not in dumped
    for message in prompt:
        assert message["content"] not in dumped


async def test_inference_test_provider_error_body_is_not_stored(
    client: AsyncClient,
    db_session,
    httpx_mock: HTTPXMock,
    priced_gpt_test: None,
) -> None:
    await configure(client)
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        status_code=500,
        json={"error": {"message": SENTINEL, "type": "server_error"}},
    )
    response = await client.post(
        f"{BASE}/providers/openai/inference-test", json={"model": "gpt-test", "confirm": True}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    found = await events(db_session, "ai.request")
    assert_not_succeeded(found)
    assert found[-1].outcome == "failed"
    assert found[-1].summary["error_code"] == response.json()["error"]["category"]
    assert SENTINEL not in await rows_json(db_session)
