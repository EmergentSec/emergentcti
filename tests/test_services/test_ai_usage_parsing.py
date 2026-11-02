"""Adapters parse provider-reported usage; anything doubtful is None (#17)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from cti.schemas.ai import AiErrorCategory
from cti.services.ai.anthropic import AnthropicAdapter
from cti.services.ai.base import AdapterUsage, AiAdapterError, parse_usage
from cti.services.ai.openai import OpenAiAdapter
from cti.services.ai.openrouter import OpenRouterAdapter
from cti.services.ai.xai import XAiAdapter

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

    from cti.services.ai.base import AiProviderAdapter

FAKE_KEY = "sk-test-not-a-real-key-usage-0000"

PROVIDERS = [
    pytest.param(
        AnthropicAdapter(),
        "https://api.anthropic.com/v1/messages",
        "input_tokens",
        "output_tokens",
        id="anthropic",
    ),
    pytest.param(
        OpenAiAdapter(),
        "https://api.openai.com/v1/chat/completions",
        "prompt_tokens",
        "completion_tokens",
        id="openai",
    ),
    pytest.param(
        OpenRouterAdapter(),
        "https://openrouter.ai/api/v1/chat/completions",
        "prompt_tokens",
        "completion_tokens",
        id="openrouter",
    ),
    pytest.param(
        XAiAdapter(),
        "https://api.x.ai/v1/chat/completions",
        "prompt_tokens",
        "completion_tokens",
        id="xai",
    ),
]


#: The output cap's request-body field, per provider (M2, #17).
MAX_TOKENS_FIELDS = {
    "anthropic": "max_tokens",  # Required by the Messages API.
    "openai": "max_completion_tokens",  # max_tokens is rejected by o-series.
    "openrouter": "max_completion_tokens",  # max_tokens is deprecated.
    "xai": "max_tokens",  # See XAiAdapter._MAX_TOKENS_FIELD.
}


@pytest.mark.parametrize(("adapter", "url", "input_field", "output_field"), PROVIDERS)
async def test_complete_parses_usage_and_sends_max_output_tokens(
    request: pytest.FixtureRequest,
    httpx_mock: HTTPXMock,
    adapter: AiProviderAdapter,
    url: str,
    input_field: str,
    output_field: str,
) -> None:
    httpx_mock.add_response(
        url=url, json={"usage": {input_field: 21, output_field: 4, "total_tokens": 25}}
    )

    usage = await adapter.complete(FAKE_KEY, "m-1", "hello", 777)

    assert usage == AdapterUsage(input_tokens=21, output_tokens=4)
    sent = httpx_mock.get_request()
    assert sent is not None
    field = MAX_TOKENS_FIELDS[request.node.callspec.id]
    assert json.loads(sent.content) == {
        "model": "m-1",
        field: 777,
        "messages": [{"role": "user", "content": "hello"}],
    }


@pytest.mark.parametrize("model", ["o1", "o3-mini", "o4-mini"])
async def test_openai_reasoning_models_get_max_completion_tokens(
    httpx_mock: HTTPXMock, model: str
) -> None:
    """o-series models reject ``max_tokens``; the cap must use the new field."""
    httpx_mock.add_response(
        url="https://api.openai.com/v1/chat/completions",
        json={"usage": {"prompt_tokens": 3, "completion_tokens": 50}},
    )

    await OpenAiAdapter().complete(FAKE_KEY, model, "hello", 512)

    sent = httpx_mock.get_request()
    assert sent is not None
    payload = json.loads(sent.content)
    assert payload["model"] == model
    assert payload["max_completion_tokens"] == 512
    assert "max_tokens" not in payload


@pytest.mark.parametrize(("adapter", "url", "input_field", "output_field"), PROVIDERS)
async def test_other_providers_field_names_are_not_read(
    httpx_mock: HTTPXMock,
    adapter: AiProviderAdapter,
    url: str,
    input_field: str,
    output_field: str,
) -> None:
    """Each provider's own names only: no guessing across conventions."""
    swapped = (
        {"prompt_tokens": 9, "completion_tokens": 9}
        if input_field == "input_tokens"
        else {"input_tokens": 9, "output_tokens": 9}
    )
    httpx_mock.add_response(url=url, json={"usage": swapped})

    assert await adapter.inference_test(FAKE_KEY, "m") == AdapterUsage(None, None)


@pytest.mark.parametrize(("adapter", "url", "input_field", "output_field"), PROVIDERS)
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"usage": None},
        {"usage": "12 tokens"},
        {"usage": [1, 2]},
    ],
    ids=["missing", "null", "string", "list"],
)
async def test_missing_usage_is_unknown_not_zero(
    httpx_mock: HTTPXMock,
    adapter: AiProviderAdapter,
    url: str,
    input_field: str,
    output_field: str,
    body: dict[str, Any],
) -> None:
    httpx_mock.add_response(url=url, json=body)

    assert await adapter.inference_test(FAKE_KEY, "m") == AdapterUsage(None, None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (5, 5),
        (-1, None),
        (True, None),
        (False, None),
        (3.0, None),
        ("7", None),
        (None, None),
        (10**12, None),
        ({"n": 1}, None),
    ],
)
def test_garbage_token_counts_become_none(value: object, expected: int | None) -> None:
    usage = parse_usage({"usage": {"in": value, "out": 2}}, "in", "out")
    assert usage == AdapterUsage(input_tokens=expected, output_tokens=2)


def test_partial_usage_keeps_the_known_count() -> None:
    assert parse_usage({"usage": {"out": 3}}, "in", "out") == AdapterUsage(None, 3)


async def test_non_object_success_body_is_provider_error_with_status(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(url="https://api.openai.com/v1/chat/completions", json=[1, 2])

    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().inference_test(FAKE_KEY, "m")

    assert caught.value.error.category == AiErrorCategory.PROVIDER_ERROR
    assert caught.value.status_code == 200
    assert caught.value.sent is True


async def test_unparseable_success_body_is_provider_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://api.x.ai/v1/chat/completions", text="<html>")

    with pytest.raises(AiAdapterError) as caught:
        await XAiAdapter().inference_test(FAKE_KEY, "m")

    assert caught.value.status_code == 200


async def test_provider_status_is_kept_on_the_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://api.anthropic.com/v1/messages", status_code=529)

    with pytest.raises(AiAdapterError) as caught:
        await AnthropicAdapter().inference_test(FAKE_KEY, "m")

    assert caught.value.status_code == 529
    assert caught.value.sent is True


async def test_header_encoding_failure_is_marked_unsent(httpx_mock: HTTPXMock) -> None:
    with pytest.raises(AiAdapterError) as caught:
        await OpenAiAdapter().inference_test("sk-\N{LATIN SMALL LETTER E WITH ACUTE}", "m")

    assert caught.value.sent is False
    assert httpx_mock.get_requests() == []


def test_adapter_hosts_name_the_destination() -> None:
    assert [a.host for a in (AnthropicAdapter(), OpenAiAdapter())] == [
        "api.anthropic.com",
        "api.openai.com",
    ]
    assert [a.host for a in (OpenRouterAdapter(), XAiAdapter())] == ["openrouter.ai", "api.x.ai"]
