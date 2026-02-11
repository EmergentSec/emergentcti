import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.enrichment import (
    EnrichmentConfigResponse,
    EnrichmentConfigUpdate,
    EnrichmentRunResponse,
    EnrichmentTriggerRequest,
    ProviderInfo,
)
from cti.services import enrichment_service

router = APIRouter()


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[ProviderInfo]:
    """List all enrichment providers with their configuration status."""
    return await enrichment_service.list_provider_info(db)


@router.get("/config", response_model=list[EnrichmentConfigResponse])
async def get_configs(
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> list[EnrichmentConfigResponse]:
    """Get all enrichment configurations (admin only)."""
    configs = await enrichment_service.get_enrichment_configs(db)
    return [EnrichmentConfigResponse.model_validate(c) for c in configs]


@router.put(
    "/config/{provider_name}",
    response_model=EnrichmentConfigResponse,
)
async def update_config(
    provider_name: str,
    data: EnrichmentConfigUpdate,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> EnrichmentConfigResponse:
    """Update or create enrichment configuration for a provider (admin only)."""
    try:
        config = await enrichment_service.update_enrichment_config(
            db, provider_name, data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
    return EnrichmentConfigResponse.model_validate(config)


@router.post(
    "/observables/{observable_id}/enrich",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_enrichment(
    observable_id: uuid.UUID,
    body: EnrichmentTriggerRequest,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger enrichment for an observable. Dispatches via Celery for async execution."""
    from cti.worker import enrich_observable_task

    if body.provider_name:
        # Single provider
        enrich_observable_task.delay(
            str(observable_id),
            body.provider_name,
            str(user.id),
        )
        return {
            "status": "triggered",
            "observable_id": str(observable_id),
            "providers": [body.provider_name],
        }
    else:
        # All enabled providers for this observable type
        from sqlalchemy import select

        from cti.enrichment.registry import PROVIDER_REGISTRY
        from cti.models.enrichment import EnrichmentConfig
        from cti.models.observable import Observable

        # Look up observable to get its type
        result = await db.execute(
            select(Observable).where(Observable.id == observable_id)
        )
        observable = result.scalar_one_or_none()
        if not observable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Observable not found",
            )

        obs_type = observable.type.value

        # Get enabled configs
        config_result = await db.execute(
            select(EnrichmentConfig).where(
                EnrichmentConfig.enabled.is_(True),
                EnrichmentConfig.api_key_encrypted.isnot(None),
            )
        )
        configs = config_result.scalars().all()

        dispatched: list[str] = []
        for config in configs:
            provider = PROVIDER_REGISTRY.get(config.provider_name)
            if provider and provider.supports_type(obs_type):
                enrich_observable_task.delay(
                    str(observable_id),
                    config.provider_name,
                    str(user.id),
                )
                dispatched.append(config.provider_name)

        return {
            "status": "triggered",
            "observable_id": str(observable_id),
            "providers": dispatched,
        }


@router.get(
    "/observables/{observable_id}/enrichments",
    response_model=list[EnrichmentRunResponse],
)
async def get_enrichment_history(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[EnrichmentRunResponse]:
    """Get enrichment history for an observable."""
    runs = await enrichment_service.get_enrichment_history(
        db, observable_id
    )
    return [EnrichmentRunResponse.model_validate(r) for r in runs]
