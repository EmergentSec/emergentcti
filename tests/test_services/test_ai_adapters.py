"""Provider adapter contract tests with no live network access."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from cti.schemas.ai import AiErrorCategory
from cti.services.ai.anthropic import AnthropicAdapter
from cti.services.ai.base import INFERENCE_PROMPT, AiAdapterError
from cti.services.ai.openai import OpenAiAdapter
from cti.services.ai.openrouter import OpenRouterAdapter
from cti.services.ai.xai import XAiAdapter

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

FAKE_KEY = "sk-test-not-a-real-key-0000"


async def test_anthropic_model_parsing_and_headers(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.anthropic.com/v1/models?limit=1000",
        json={
            "data": [
                {"id": "claude-b", "display_name": "Zulu"},
                {"id": "claude-a"},
            ]
        },
    )

    models = await AnthropicAdapter().list_models(FAKE_KEY)

    assert [(model.id, model.name) for model in models] == [
        ("claude-a", "claude-a"),
        ("claude-b", "Zulu"),
    ]
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["x-api-key"] == FAKE_KEY
    assert request.headers["anthropic-version"] == "2023-06-01"


async def test_openai_model_filtering_and_sorting(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        json={
            "data": [
                {"id": "z-chat"},
                {"id": "text-embedding-3-small"},
                {"id": "dall-e-3"},
                {"id": "a-chat"},
                {"id": "gpt-realtime"},
            ]
        },
    )

    models = await OpenAiAdapter().list_models(FAKE_KEY)

    assert [model.id for model in models] == ["a-chat", "z-chat"]
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"


async def test_openrouter_filters_non_text_and_parses_context(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/models",
        json={
            "data": [
                {
                    "id": "provider/text",
                    "name": "Text model",
                    "context_length": 128000,
                    "architecture": {"output_modalities": ["text"]},
                },
                {
                    "id": "provider/image",
                    "name": "Image model",
                    "architecture": {"output_modalities": ["image"]},
                },
                {"id": "provider/unknown"},
            ]
        },
    )

    models = await OpenRouterAdapter().list_models(FAKE_KEY)

    assert [model.id for model in models] == ["provider/unknown", "provider/text"]
    assert models[1].context_length == 128000


async def test_xai_model_parsing(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.x.ai/v1/models",
        json={"data": [{"id": "grok-z"}, {"id": "grok-a"}]},
    )

    models = await XAiAdapter().list_models(FAKE_KEY)

    assert [model.id for model in models] == ["grok-a", "grok-z"]


@pytest.mark.parametrize(
    ("adapter", "url", "payload"),
    [
        (
            AnthropicAdapter(),
            "https://api.anthropic.com/v1/models?limit=1000",
            {"data": []},
        ),
        (OpenAiAdapter(), "https://api.openai.com/v1/models", {"data": []}),
        (OpenRouterAdapter(), "https://openrouter.ai/api/v1/key", {"data": {}}),
        (XAiAdapter(), "https://api.x.ai/v1/models", {"data": []}),
    ],
)
async def test_each_adapter_non_billable_check(
    httpx_mock: HTTPXMock,
    adapter: object,
    url: str,
    payload: dict,
) -> None:
    httpx_mock.add_response(url=url, json=payload)

    await adapter.check(FAKE_KEY)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (401, AiErrorCategory.INVALID_CREDENTIALS),
        (403, AiErrorCategory.PERMISSION_DENIED),
        (402, AiErrorCategory.INSUFFICIENT_QUOTA),
        (429, AiErrorCategory.RATE_LIMITED),
        (404, AiErrorCategory.MODEL_UNAVAILABLE),
        (500, AiErrorCategory.PROVIDER_ERROR),
        (503, AiErrorCategory.PROVIDER_ERROR),
    ],
)
async def test_http_status_mapping(
    httpx_mock: HTTPXMock,
    status_code: int,
    category: AiErrorCategory,
) -> None:
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        status_code=status_code,
    )

    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().list_models(FAKE_KEY)

    assert caught.value.error.category == category
    assert FAKE_KEY not in caught.value.error.message


async def test_provider_body_can_identify_quota_without_leaking_it(
    httpx_mock: HTTPXMock,
) -> None:
    raw_body = "billing credits exhausted for secret account"
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models",
        status_code=403,
        text=raw_body,
    )

    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().list_models(FAKE_KEY)

    assert caught.value.error.category == AiErrorCategory.INSUFFICIENT_QUOTA
    assert raw_body not in caught.value.error.message


@pytest.mark.parametrize(
    ("exception", "category"),
    [
        (httpx.ReadTimeout("timed out"), AiErrorCategory.TIMEOUT),
        (httpx.ConnectError("network failed"), AiErrorCategory.NETWORK_ERROR),
    ],
)
async def test_transport_error_mapping(
    httpx_mock: HTTPXMock,
    exception: Exception,
    category: AiErrorCategory,
) -> None:
    httpx_mock.add_exception(exception, url="https://api.openai.com/v1/models")

    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().list_models(FAKE_KEY)

    assert caught.value.error.category == category


@pytest.mark.parametrize("operation", ["check", "models", "inference"])
async def test_header_encoding_errors_are_sanitized_for_every_operation(
    httpx_mock: HTTPXMock,
    operation: str,
) -> None:
    raw_key = "sk-test-\N{LATIN SMALL LETTER E WITH ACUTE}-secret"
    adapter = OpenAiAdapter()

    with pytest.raises(AiAdapterError) as caught:
        if operation == "check":
            await adapter.check(raw_key)
        elif operation == "models":
            await adapter.list_models(raw_key)
        else:
            await adapter.inference_test(raw_key, "gpt-test")

    assert caught.value.error.category == AiErrorCategory.NETWORK_ERROR
    assert raw_key not in caught.value.error.message
    assert httpx_mock.get_requests() == []


async def test_unparseable_success_is_provider_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://api.openai.com/v1/models", text="not-json")

    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().list_models(FAKE_KEY)

    assert caught.value.error.category == AiErrorCategory.PROVIDER_ERROR


async def test_inference_uses_only_fixed_bounded_prompt(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={"choices": []},
    )

    await OpenAiAdapter().inference_test(FAKE_KEY, "gpt-test")

    request = httpx_mock.get_request()
    assert request is not None
    payload = __import__("json").loads(request.content)
    assert payload == {
        "model": "gpt-test",
        "max_completion_tokens": 16,
        "messages": [{"role": "user", "content": INFERENCE_PROMPT}],
    }
