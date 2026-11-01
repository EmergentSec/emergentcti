from __future__ import annotations

from cti.schemas.ai import AiErrorCategory, AiModel
from cti.services.ai.base import (
    INFERENCE_PROMPT,
    AiAdapterError,
    AiProviderAdapter,
    make_ai_error,
    parse_json,
    sorted_models,
)


class OpenRouterAdapter(AiProviderAdapter):
    _BASE_URL = "https://openrouter.ai/api/v1"

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
            architecture = item.get("architecture")
            if isinstance(architecture, dict):
                output_modalities = architecture.get("output_modalities")
                if isinstance(output_modalities, list) and "text" not in output_modalities:
                    continue
            model_id = item["id"]
            name = item.get("name")
            context_length = item.get("context_length")
            models.append(
                AiModel(
                    id=model_id,
                    name=name if isinstance(name, str) else model_id,
                    context_length=context_length if isinstance(context_length, int) else None,
                )
            )
        return sorted_models(models)

    async def check(self, api_key: str) -> None:
        response = await self._request(
            "GET",
            f"{self._BASE_URL}/key",
            headers=self._headers(api_key),
        )
        if not isinstance(parse_json(response), dict):
            raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR))

    async def inference_test(self, api_key: str, model: str) -> None:
        response = await self._request(
            "POST",
            f"{self._BASE_URL}/chat/completions",
            headers=self._headers(api_key),
            json={
                "model": model,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": INFERENCE_PROMPT}],
            },
        )
        if not isinstance(parse_json(response), dict):
            raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR))
