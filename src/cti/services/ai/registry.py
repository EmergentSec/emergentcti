from __future__ import annotations

from typing import TYPE_CHECKING

from cti.models.ai import AiProvider
from cti.services.ai.anthropic import AnthropicAdapter
from cti.services.ai.openai import OpenAiAdapter
from cti.services.ai.openrouter import OpenRouterAdapter
from cti.services.ai.xai import XAiAdapter

if TYPE_CHECKING:
    from cti.services.ai.base import AiProviderAdapter

_ADAPTERS: dict[AiProvider, AiProviderAdapter] = {
    AiProvider.ANTHROPIC: AnthropicAdapter(),
    AiProvider.OPENAI: OpenAiAdapter(),
    AiProvider.OPENROUTER: OpenRouterAdapter(),
    AiProvider.XAI: XAiAdapter(),
}


def get_adapter(provider: AiProvider) -> AiProviderAdapter:
    return _ADAPTERS[provider]
