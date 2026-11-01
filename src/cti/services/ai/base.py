from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from cti.schemas.ai import AiError, AiErrorCategory, AiModel

REQUEST_TIMEOUT_SECONDS = 10.0
INFERENCE_PROMPT = "Reply with the single word: OK"

_ERROR_MESSAGES: dict[AiErrorCategory, str] = {
    AiErrorCategory.INVALID_CREDENTIALS: "The provider rejected the API key.",
    AiErrorCategory.PERMISSION_DENIED: (
        "The API key does not have permission for this operation."
    ),
    AiErrorCategory.RATE_LIMITED: "The provider rate limit was reached. Try again later.",
    AiErrorCategory.INSUFFICIENT_QUOTA: (
        "The provider account has insufficient quota or billing capacity."
    ),
    AiErrorCategory.MODEL_UNAVAILABLE: "The requested model is unavailable.",
    AiErrorCategory.TIMEOUT: "The provider request timed out.",
    AiErrorCategory.NETWORK_ERROR: "The provider could not be reached.",
    AiErrorCategory.PROVIDER_ERROR: "The provider returned an unexpected response.",
    AiErrorCategory.NOT_CONFIGURED: "The provider is not configured.",
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
    def __init__(self, error: AiError) -> None:
        super().__init__(error.category.value)
        self.error = error


def _raise_for_provider_status(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    category = category_for_http_status(
        response.status_code,
        quota_or_billing_error=_response_mentions_quota(response),
    )
    raise AiAdapterError(make_ai_error(category, status_code=response.status_code))


def parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except (ValueError, TypeError):
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR)) from None


class AiProviderAdapter(ABC):
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
        except httpx.TimeoutException:
            raise AiAdapterError(make_ai_error(AiErrorCategory.TIMEOUT)) from None
        except httpx.RequestError:
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
    async def inference_test(self, api_key: str, model: str) -> None:
        """Send the fixed, explicitly confirmed inference prompt."""


def sorted_models(models: list[AiModel]) -> list[AiModel]:
    return sorted(models, key=lambda model: (model.name.casefold(), model.id))
