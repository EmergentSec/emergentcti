from __future__ import annotations

from cti.schemas.ai import AiErrorCategory, AiModel
from cti.services.ai.base import (
    AdapterUsage,
    AiAdapterError,
    AiProviderAdapter,
    make_ai_error,
    parse_json,
    sorted_models,
)


class XAiAdapter(AiProviderAdapter):
    _BASE_URL = "https://api.x.ai/v1"
    # Kept as ``max_tokens``: xAI's OpenAI-compatible chat completions has long
    # accepted it, and support for ``max_completion_tokens`` could not be
    # confirmed from xAI's published reference when this was written (#17).
    # Switch only after verifying it, so a cap is never silently ignored.
    _MAX_TOKENS_FIELD = "max_tokens"

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    async def list_models(self, api_key: str) -> list[AiModel]:
        response = await self._request(
            "GET",
            f"{self._BASE_URL}/models",
            headers=self._headers(api_key),
        )
        payload = parse_json(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR))

        models: list[AiModel] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = item["id"]
            models.append(AiModel(id=model_id, name=model_id))
        return sorted_models(models)

    async def complete(
        self,
        api_key: str,
        model: str,
        prompt: str,
        max_output_tokens: int,
        *,
        timeout: float = 180.0,
    ) -> AdapterUsage:
        return await self._post_message(
            f"{self._BASE_URL}/chat/completions",
            headers=self._headers(api_key),
            model=model,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            input_field="prompt_tokens",
            output_field="completion_tokens",
            timeout=timeout,
        )
