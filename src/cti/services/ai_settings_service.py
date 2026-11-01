from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import TYPE_CHECKING

from sqlalchemy import select

from cti.core.security import decrypt_config, encrypt_config
from cti.models.ai import AiProvider, AiProviderConfig, AiSettingsRecord
from cti.schemas.ai import (
    AiCheckResult,
    AiDefault,
    AiDefaultUpdate,
    AiError,
    AiErrorCategory,
    AiInferenceResult,
    AiModel,
    AiModelList,
    AiProviderStatus,
    AiSettings,
    ModelSource,
)
from cti.services.ai.base import AiAdapterError, make_ai_error, sorted_models
from cti.services.ai.catalog import fallback_models
from cti.services.ai.registry import get_adapter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MODEL_CACHE_TTL = timedelta(hours=1)

_PROVIDER_METADATA: dict[AiProvider, tuple[str, str]] = {
    AiProvider.ANTHROPIC: ("Anthropic", "https://console.anthropic.com/settings/keys"),
    AiProvider.OPENAI: ("OpenAI", "https://platform.openai.com/api-keys"),
    AiProvider.OPENROUTER: ("OpenRouter", "https://openrouter.ai/settings/keys"),
    AiProvider.XAI: ("xAI (Grok)", "https://console.x.ai/"),
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AiSettingsServiceError(Exception):
    def __init__(self, status_code: int, error: AiError) -> None:
        super().__init__(error.category.value)
        self.status_code = status_code
        self.error = error


def _provider_status(
    provider: AiProvider,
    config: AiProviderConfig | None,
) -> AiProviderStatus:
    display_name, setup_url = _PROVIDER_METADATA[provider]
    return AiProviderStatus(
        provider=provider,
        display_name=display_name,
        configured=config is not None,
        key_hint=config.key_hint if config is not None else None,
        models_fetched_at=config.models_fetched_at if config is not None else None,
        last_check_status=config.last_check_status if config is not None else None,
        last_check_category=(
            AiErrorCategory(config.last_check_category)
            if config is not None and config.last_check_category is not None
            else None
        ),
        last_checked_at=config.last_checked_at if config is not None else None,
        setup_url=setup_url,
    )


async def _get_provider_config(
    db: AsyncSession,
    provider: AiProvider,
) -> AiProviderConfig | None:
    return await db.scalar(
        select(AiProviderConfig).where(AiProviderConfig.provider == provider)
    )


async def _require_provider_config(
    db: AsyncSession,
    provider: AiProvider,
    *,
    status_code: int = 409,
) -> AiProviderConfig:
    config = await _get_provider_config(db, provider)
    if config is None:
        raise AiSettingsServiceError(
            status_code,
            make_ai_error(AiErrorCategory.NOT_CONFIGURED),
        )
    return config


def _decrypt_api_key(config: AiProviderConfig) -> str:
    try:
        payload = decrypt_config(config.credentials_encrypted)
        api_key = payload["api_key"]
    except Exception:  # the encrypted payload must never escape through the error
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR)) from None
    if not isinstance(api_key, str) or not api_key:
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR))
    return api_key


def _cached_models(config: AiProviderConfig) -> list[AiModel] | None:
    if config.model_cache is None:
        return None
    try:
        return [AiModel.model_validate(model) for model in config.model_cache]
    except (TypeError, ValueError):
        return None


async def _flush_with_orphan_cleanup(db: AsyncSession) -> None:
    settings = await db.get(AiSettingsRecord, 1)
    if (
        settings is not None
        and settings.default_provider is None
        and settings.default_model is not None
    ):
        settings.default_model = None
        settings.default_model_is_custom = False
    await db.flush()


async def get_settings(db: AsyncSession) -> AiSettings:
    configured = {
        AiProvider(item.provider): item
        for item in (await db.scalars(select(AiProviderConfig))).all()
    }
    settings = await db.get(AiSettingsRecord, 1)
    default = None
    if (
        settings is not None
        and settings.default_provider is not None
        and settings.default_model is not None
    ):
        default = AiDefault(
            provider=AiProvider(settings.default_provider),
            model=settings.default_model,
            is_custom=settings.default_model_is_custom,
        )
    return AiSettings(
        providers=[_provider_status(provider, configured.get(provider)) for provider in AiProvider],
        default=default,
    )


async def save_provider_key(
    db: AsyncSession,
    provider: AiProvider,
    api_key: str,
) -> AiProviderStatus:
    config = await _get_provider_config(db, provider)
    encrypted = encrypt_config({"api_key": api_key})
    key_hint = api_key[-4:] if len(api_key) >= 12 else None
    if config is None:
        config = AiProviderConfig(
            provider=provider,
            credentials_encrypted=encrypted,
            key_hint=key_hint,
        )
        db.add(config)
    else:
        config.credentials_encrypted = encrypted
        config.key_hint = key_hint
        config.model_cache = None
        config.models_fetched_at = None
        config.last_check_status = None
        config.last_check_category = None
        config.last_checked_at = None
    await _flush_with_orphan_cleanup(db)
    return _provider_status(provider, config)


async def delete_provider(db: AsyncSession, provider: AiProvider) -> None:
    config = await _require_provider_config(db, provider, status_code=404)
    settings = await db.get(AiSettingsRecord, 1)
    if settings is not None and settings.default_provider == provider:
        settings.default_provider = None
        settings.default_model = None
        settings.default_model_is_custom = False
    await db.delete(config)
    await _flush_with_orphan_cleanup(db)


async def check_provider(db: AsyncSession, provider: AiProvider) -> AiCheckResult:
    config = await _require_provider_config(db, provider)
    checked_at = _now()
    try:
        api_key = _decrypt_api_key(config)
        await get_adapter(provider).check(api_key)
    except AiAdapterError as exc:
        config.last_check_status = "error"
        config.last_check_category = exc.error.category.value
        config.last_checked_at = checked_at
        await _flush_with_orphan_cleanup(db)
        return AiCheckResult(ok=False, error=exc.error, checked_at=checked_at)

    config.last_check_status = "ok"
    config.last_check_category = None
    config.last_checked_at = checked_at
    await _flush_with_orphan_cleanup(db)
    return AiCheckResult(ok=True, error=None, checked_at=checked_at)


async def list_models(
    db: AsyncSession,
    provider: AiProvider,
    *,
    refresh: bool,
) -> AiModelList:
    config = await _require_provider_config(db, provider)
    cached = _cached_models(config)
    now = _now()
    if (
        not refresh
        and cached is not None
        and config.models_fetched_at is not None
        and now - config.models_fetched_at < MODEL_CACHE_TTL
    ):
        return AiModelList(
            provider=provider,
            source=ModelSource.CACHE,
            fetched_at=config.models_fetched_at,
            models=cached,
            error=None,
        )

    try:
        api_key = _decrypt_api_key(config)
        models = await get_adapter(provider).list_models(api_key)
    except AiAdapterError as exc:
        if cached is not None:
            return AiModelList(
                provider=provider,
                source=ModelSource.CACHE,
                fetched_at=config.models_fetched_at,
                models=cached,
                error=exc.error,
            )
        return AiModelList(
            provider=provider,
            source=ModelSource.FALLBACK,
            fetched_at=None,
            models=sorted_models(fallback_models(provider)),
            error=exc.error,
        )

    fetched_at = _now()
    config.model_cache = [model.model_dump(mode="json") for model in models]
    config.models_fetched_at = fetched_at
    await _flush_with_orphan_cleanup(db)
    return AiModelList(
        provider=provider,
        source=ModelSource.LIVE,
        fetched_at=fetched_at,
        models=models,
        error=None,
    )


async def set_default(
    db: AsyncSession,
    update: AiDefaultUpdate,
) -> AiDefault:
    config = await _require_provider_config(db, update.provider)
    if not update.is_custom:
        candidates = _cached_models(config)
        if candidates is None:
            candidates = fallback_models(update.provider)
        if update.model not in {model.id for model in candidates}:
            raise AiSettingsServiceError(
                422,
                AiError(
                    category=AiErrorCategory.MODEL_UNAVAILABLE,
                    message=(
                        "That model is not in the stored provider model list. "
                        "Choose a listed model or use a custom ID."
                    ),
                ),
            )

    settings = await db.get(AiSettingsRecord, 1)
    if settings is None:
        settings = AiSettingsRecord(id=1)
        db.add(settings)
    settings.default_provider = update.provider
    settings.default_model = update.model
    settings.default_model_is_custom = update.is_custom
    await _flush_with_orphan_cleanup(db)
    return AiDefault(
        provider=update.provider,
        model=update.model,
        is_custom=update.is_custom,
    )


async def clear_default(db: AsyncSession) -> None:
    settings = await db.get(AiSettingsRecord, 1)
    if settings is None:
        return
    settings.default_provider = None
    settings.default_model = None
    settings.default_model_is_custom = False
    await _flush_with_orphan_cleanup(db)


async def inference_test(
    db: AsyncSession,
    provider: AiProvider,
    model: str,
) -> AiInferenceResult:
    config = await _require_provider_config(db, provider)
    started_at = perf_counter()
    try:
        api_key = _decrypt_api_key(config)
        await get_adapter(provider).inference_test(api_key, model)
    except AiAdapterError as exc:
        return AiInferenceResult(ok=False, error=exc.error, latency_ms=None)
    latency_ms = round((perf_counter() - started_at) * 1000)
    return AiInferenceResult(ok=True, error=None, latency_ms=latency_ms)
