from __future__ import annotations

from cti.models.ai import AiProvider
from cti.schemas.ai import AiModel

# Manually maintained convenience catalogs. Provider catalogs change frequently, so
# these small fallback lists may go stale and the custom-model path must remain available.
FALLBACK_CATALOG: dict[AiProvider, tuple[AiModel, ...]] = {
    AiProvider.ANTHROPIC: (
        AiModel(id="claude-sonnet-4-5", name="Claude Sonnet 4.5"),
        AiModel(id="claude-haiku-4-5", name="Claude Haiku 4.5"),
    ),
    AiProvider.OPENAI: (
        AiModel(id="gpt-5", name="GPT-5"),
        AiModel(id="gpt-5-mini", name="GPT-5 mini"),
    ),
    AiProvider.OPENROUTER: (
        AiModel(id="anthropic/claude-sonnet-4.5", name="Claude Sonnet 4.5"),
        AiModel(id="openai/gpt-5", name="GPT-5"),
    ),
    AiProvider.XAI: (
        AiModel(id="grok-4", name="Grok 4"),
        AiModel(id="grok-4-fast", name="Grok 4 Fast"),
    ),
}


def fallback_models(provider: AiProvider) -> list[AiModel]:
    return [model.model_copy() for model in FALLBACK_CATALOG[provider]]
