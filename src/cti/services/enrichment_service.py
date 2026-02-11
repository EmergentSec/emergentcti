import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.security import decrypt_config, encrypt_config
from cti.enrichment.registry import PROVIDER_REGISTRY, get_enrichment_provider
from cti.models.enrichment import EnrichmentConfig, EnrichmentRun, EnrichmentRunStatus
from cti.models.observable import Observable
from cti.schemas.enrichment import EnrichmentConfigUpdate, ProviderInfo

logger = logging.getLogger(__name__)


async def list_provider_info(db: AsyncSession) -> list[ProviderInfo]:
    """List all providers from registry with their config status."""
    # Fetch all configs in one query
    result = await db.execute(select(EnrichmentConfig))
    configs = {c.provider_name: c for c in result.scalars().all()}

    providers: list[ProviderInfo] = []
    for name, provider in PROVIDER_REGISTRY.items():
        config = configs.get(name)
        providers.append(
            ProviderInfo(
                name=name,
                supported_types=provider.supported_types,
                configured=config is not None and config.api_key_encrypted is not None,
                enabled=config.enabled if config else False,
            )
        )
    return providers


async def get_enrichment_configs(db: AsyncSession) -> list[EnrichmentConfig]:
    """List all enrichment configurations."""
    result = await db.execute(
        select(EnrichmentConfig).order_by(EnrichmentConfig.priority)
    )
    return list(result.scalars().all())


async def update_enrichment_config(
    db: AsyncSession,
    provider_name: str,
    data: EnrichmentConfigUpdate,
) -> EnrichmentConfig:
    """Upsert enrichment config. Encrypt API key if provided."""
    # Verify provider exists in registry
    provider = get_enrichment_provider(provider_name)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_name}")

    # Try to find existing config
    result = await db.execute(
        select(EnrichmentConfig).where(
            EnrichmentConfig.provider_name == provider_name
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Create new config
        config = EnrichmentConfig(provider_name=provider_name)
        db.add(config)

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    api_key = update_data.pop("api_key", None)

    for field, value in update_data.items():
        setattr(config, field, value)

    if api_key is not None:
        config.api_key_encrypted = encrypt_config(api_key)

    await db.flush()
    await db.refresh(config)
    return config


async def enrich_observable(
    db: AsyncSession,
    observable_id: str | uuid.UUID,
    provider_name: str,
    user_id: str | uuid.UUID | None = None,
) -> EnrichmentRun:
    """Run a single enrichment provider against an observable."""
    observable_id = uuid.UUID(str(observable_id))
    user_uuid = uuid.UUID(str(user_id)) if user_id else None

    # Look up observable
    result = await db.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    observable = result.scalar_one_or_none()
    if not observable:
        raise ValueError(f"Observable not found: {observable_id}")

    # Get provider from registry
    provider = get_enrichment_provider(provider_name)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_name}")

    # Verify provider supports this observable type
    obs_type = observable.type.value
    if not provider.supports_type(obs_type):
        raise ValueError(
            f"Provider {provider_name} does not support type {obs_type}"
        )

    # Get API key from config
    config_result = await db.execute(
        select(EnrichmentConfig).where(
            EnrichmentConfig.provider_name == provider_name
        )
    )
    config = config_result.scalar_one_or_none()
    if not config or not config.api_key_encrypted:
        raise ValueError(
            f"Provider {provider_name} is not configured with an API key"
        )

    api_key = decrypt_config(config.api_key_encrypted)

    # Create enrichment run record
    run = EnrichmentRun(
        observable_id=observable_id,
        provider_name=provider_name,
        status=EnrichmentRunStatus.running,
        started_at=datetime.now(UTC),
        triggered_by=user_uuid,
    )
    db.add(run)
    await db.flush()

    # Execute enrichment
    try:
        enrichment_result = await provider.enrich(
            obs_type, observable.value, api_key
        )

        if enrichment_result.success:
            run.status = EnrichmentRunStatus.success
            run.result_data = enrichment_result.data
            run.summary = enrichment_result.summary

            # Update observable confidence based on enrichment data
            try:
                from cti.services.confidence_service import (
                    compute_provider_confidence,
                    update_observable_confidence,
                )

                provider_score = compute_provider_confidence(
                    provider_name, enrichment_result.data or {}
                )
                if provider_score is not None:
                    await update_observable_confidence(
                        db, observable_id, provider_score
                    )
            except Exception:
                logger.warning(
                    "Failed to update confidence from enrichment",
                    exc_info=True,
                )
        else:
            run.status = EnrichmentRunStatus.failure
            run.error_message = enrichment_result.error

        run.completed_at = datetime.now(UTC)

    except Exception as e:
        logger.error(
            "Enrichment failed for %s/%s: %s",
            provider_name,
            observable_id,
            e,
        )
        run.status = EnrichmentRunStatus.failure
        run.error_message = str(e)
        run.completed_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(run)
    return run


async def enrich_observable_all(
    db: AsyncSession,
    observable_id: str | uuid.UUID,
    user_id: str | uuid.UUID | None = None,
) -> list[EnrichmentRun]:
    """Run all enabled providers that support this observable type."""
    observable_id = uuid.UUID(str(observable_id))

    # Look up observable
    result = await db.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    observable = result.scalar_one_or_none()
    if not observable:
        raise ValueError(f"Observable not found: {observable_id}")

    obs_type = observable.type.value

    # Get all enabled configs with API keys, ordered by priority
    config_result = await db.execute(
        select(EnrichmentConfig)
        .where(
            EnrichmentConfig.enabled.is_(True),
            EnrichmentConfig.api_key_encrypted.isnot(None),
        )
        .order_by(EnrichmentConfig.priority)
    )
    configs = config_result.scalars().all()

    runs: list[EnrichmentRun] = []
    for config in configs:
        provider = get_enrichment_provider(config.provider_name)
        if provider and provider.supports_type(obs_type):
            run = await enrich_observable(
                db, observable_id, config.provider_name, user_id
            )
            runs.append(run)

    return runs


async def get_enrichment_history(
    db: AsyncSession,
    observable_id: uuid.UUID,
    limit: int = 50,
) -> list[EnrichmentRun]:
    """List enrichment runs for an observable, ordered by created_at desc."""
    result = await db.execute(
        select(EnrichmentRun)
        .where(EnrichmentRun.observable_id == observable_id)
        .order_by(EnrichmentRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
