from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from cti.schemas.ai import AiError, AiErrorCategory, AiModel

REQUEST_TIMEOUT_SECONDS = 10.0
INFERENCE_PROMPT = "Reply with the single word: OK"
#: ``max_tokens`` sent by a direct ``inference_test`` call. The gateway always
#: passes the usage policy's ``max_output_tokens`` instead.
DEFAULT_INFERENCE_MAX_OUTPUT_TOKENS = 16
#: Token counts above this are treated as garbage, not usage.
_MAX_REPORTED_TOKENS = 1_000_000_000

_ERROR_MESSAGES: dict[AiErrorCategory, str] = {
    AiErrorCategory.INVALID_CREDENTIALS: "The provider rejected the API key.",
    AiErrorCategory.PERMISSION_DENIED: ("The API key does not have permission for this operation."),
    AiErrorCategory.RATE_LIMITED: "The provider rate limit was reached. Try again later.",
    AiErrorCategory.INSUFFICIENT_QUOTA: (
        "The provider account has insufficient quota or billing capacity."
    ),
    AiErrorCategory.MODEL_UNAVAILABLE: "The requested model is unavailable.",
    AiErrorCategory.TIMEOUT: "The provider request timed out.",
    AiErrorCategory.NETWORK_ERROR: "The provider could not be reached.",
    AiErrorCategory.PROVIDER_ERROR: "The provider returned an unexpected response.",
    AiErrorCategory.NOT_CONFIGURED: "The provider is not configured.",
    AiErrorCategory.BUDGET_EXCEEDED: (
        "The local monthly AI budget would be exceeded. Budgets are local estimates, "
        "not a provider billing limit."
    ),
    AiErrorCategory.CONCURRENCY_LIMIT: (
        "Too many AI requests are already in progress. Try again shortly."
    ),
    AiErrorCategory.LOCAL_RATE_LIMITED: (
        "The local AI request rate limit was reached. Try again in a minute."
    ),
    AiErrorCategory.MODEL_BLOCKED_UNPRICED: (
        "This model has no pricing and the usage policy blocks unpriced models."
    ),
    AiErrorCategory.SHARING_FORBIDDEN: (
        "Sharing this content with an external AI provider is not allowed."
    ),
    AiErrorCategory.SHARING_NOT_APPROVED: (
        "The content to send was not approved for this provider and model."
    ),
}


def make_ai_error(
    category: AiErrorCategory,
    *,
    status_code: int | None = None,
) -> AiError:
    message = _ERROR_MESSAGES[category]
    if status_code is not None:
        message = f"{message} (HTTP {status_code})"
    return AiError(category=category, message=message)


def category_for_http_status(
    status_code: int,
    *,
    quota_or_billing_error: bool = False,
) -> AiErrorCategory:
    if quota_or_billing_error or status_code == 402:
        return AiErrorCategory.INSUFFICIENT_QUOTA
    if status_code == 401:
        return AiErrorCategory.INVALID_CREDENTIALS
    if status_code == 403:
        return AiErrorCategory.PERMISSION_DENIED
    if status_code == 404:
        return AiErrorCategory.MODEL_UNAVAILABLE
    if status_code == 429:
        return AiErrorCategory.RATE_LIMITED
    return AiErrorCategory.PROVIDER_ERROR


def _response_mentions_quota(response: httpx.Response) -> bool:
    # The body is inspected only for categorisation. It is never returned or logged.
    body = response.text[:8192].casefold()
    return any(
        marker in body
        for marker in ("quota", "billing", "insufficient_funds", "insufficient funds", "credits")
    )


class AiAdapterError(Exception):
    """A provider call failed. Never carries provider text beyond the fixed message.

    ``status_code`` is the provider's HTTP status when one was received.
    ``sent`` is False only when the request provably never left the process
    (connection refused, invalid header); accounting treats every other
    failure as possibly billable.
    """

    def __init__(
        self,
        error: AiError,
        *,
        status_code: int | None = None,
        sent: bool = True,
    ) -> None:
        super().__init__(error.category.value)
        self.error = error
        self.status_code = status_code
        self.sent = sent


@dataclass(frozen=True, slots=True)
class AdapterUsage:
    """Provider-reported token usage. ``None`` means the provider did not say."""

    input_tokens: int | None
    output_tokens: int | None


def _token_count(value: object) -> int | None:
    # bool is an int subclass; a float, string or negative number is garbage.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > _MAX_REPORTED_TOKENS:
        return None
    return value


def parse_usage(payload: object, input_field: str, output_field: str) -> AdapterUsage:
    """Read ``payload["usage"]``; anything missing or invalid becomes None."""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return AdapterUsage(input_tokens=None, output_tokens=None)
    return AdapterUsage(
        input_tokens=_token_count(usage.get(input_field)),
        output_tokens=_token_count(usage.get(output_field)),
    )


def _raise_for_provider_status(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    category = category_for_http_status(
        response.status_code,
        quota_or_billing_error=_response_mentions_quota(response),
    )
    raise AiAdapterError(
        make_ai_error(category, status_code=response.status_code),
        status_code=response.status_code,
    )


def parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (ValueError, TypeError):
        raise AiAdapterError(
            make_ai_error(AiErrorCategory.PROVIDER_ERROR), status_code=response.status_code
        ) from None


class AiProviderAdapter(ABC):
    _BASE_URL: str = ""

    @property
    def host(self) -> str:
        """The provider API host requests go to (shown before an inference is sent)."""
        return httpx.URL(self._BASE_URL).host

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.ConnectTimeout:
            raise AiAdapterError(make_ai_error(AiErrorCategory.TIMEOUT), sent=False) from None
        except httpx.TimeoutException:
            raise AiAdapterError(make_ai_error(AiErrorCategory.TIMEOUT)) from None
        except (httpx.ConnectError, httpx.UnsupportedProtocol, UnicodeError):
            # Never reached the provider: no connection, or a header that could
            # not be encoded (raised before anything is written).
            raise AiAdapterError(make_ai_error(AiErrorCategory.NETWORK_ERROR), sent=False) from None
        except Exception:
            raise AiAdapterError(make_ai_error(AiErrorCategory.NETWORK_ERROR)) from None
        _raise_for_provider_status(response)
        return response

    @abstractmethod
    async def list_models(self, api_key: str) -> list[AiModel]:
        """Return the provider's available text-generation models."""

    async def check(self, api_key: str) -> None:
        """Perform a non-billable credential check."""
        await self.list_models(api_key)

    @abstractmethod
    async def complete(
        self,
        api_key: str,
        model: str,
        prompt: str,
        max_output_tokens: int,
    ) -> AdapterUsage:
        """Send one user message with ``max_output_tokens`` as the provider's
        max-tokens parameter, and return the provider-reported usage.

        Only :mod:`cti.services.ai.gateway` may call this for accounted actions.
        """

    async def inference_test(
        self,
        api_key: str,
        model: str,
        max_output_tokens: int = DEFAULT_INFERENCE_MAX_OUTPUT_TOKENS,
    ) -> AdapterUsage:
        """Send the fixed, explicitly confirmed inference prompt."""
        return await self.complete(api_key, model, INFERENCE_PROMPT, max_output_tokens)

    async def _post_message(
        self,
        url: str,
        *,
        headers: dict[str, str],
        model: str,
        prompt: str,
        max_output_tokens: int,
        input_field: str,
        output_field: str,
    ) -> AdapterUsage:
        response = await self._request(
            "POST",
            url,
            headers=headers,
            json={
                "model": model,
                "max_tokens": max_output_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        payload = parse_json(response)
        if not isinstance(payload, dict):
            raise AiAdapterError(
                make_ai_error(AiErrorCategory.PROVIDER_ERROR), status_code=response.status_code
            )
        return parse_usage(payload, input_field, output_field)


def sorted_models(models: list[AiModel]) -> list[AiModel]:
    return sorted(models, key=lambda model: (model.name.casefold(), model.id))
