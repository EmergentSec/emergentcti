"""Admin-only AI provider configuration endpoints."""
# ruff: noqa: B008, TC002, TC003

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, require_admin
from cti.models.ai import AiProvider, AiSettingsRecord
from cti.schemas.ai import (
    AiCheckResult,
    AiDefault,
    AiDefaultUpdate,
    AiError,
    AiInferencePreview,
    AiInferenceResult,
    AiInferenceTestRequest,
    AiModelList,
    AiModelPricingList,
    AiModelPricingOut,
    AiModelPricingUpdate,
    AiProviderKeyUpdate,
    AiProviderStatus,
    AiSettings,
    AiUsagePolicyOut,
    AiUsagePolicyUpdate,
    AiUsageRecordPage,
    AiUsageReport,
    parse_month,
    validate_model_id,
)
from cti.services import ai_settings_service, audit
from cti.services.ai import gateway

router = APIRouter()


def _error_response(error: ai_settings_service.AiSettingsServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=error.error.model_dump(mode="json"),
    )


# ── Audit helpers ────────────────────────────────────────────────────


async def _record_failure(
    db: AsyncSession,
    actor: audit.Actor,
    action: str,
    resource_type: str,
    *,
    resource_id: str | None,
    status: int,
    error_code: str,
    extra: dict[str, object] | None = None,
) -> None:
    """Record a failed attempt. Roll back first: nothing from it is kept."""
    await db.rollback()
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=audit.AuditOutcome.FAILED,
        summary={**(extra or {}), "error_code": error_code, "status": status},
        strict=False,
    )


class _AiRequestAudit:
    """``ai.request`` events for one outbound provider call.

    ``begin`` is handed to the service as ``before_provider_call``: it writes
    ``initiated`` (strict) just before the provider is contacted, so a failed
    write means a 503 and no provider call. A cached model listing never calls
    it, so serving the cache records no ``ai.request``. Summaries carry only
    ``{operation, provider, model, error_code}``: never the prompt, the
    response text or a provider error message.
    """

    def __init__(
        self, actor: audit.Actor, operation: str, provider: AiProvider, model: str | None
    ) -> None:
        self.actor = actor
        self.provider = provider.value
        self.meta: dict[str, object] = {
            "operation": operation,
            "provider": provider.value,
            "model": model,
        }
        self.disclosure: audit.Disclosure | None = None

    async def begin(self) -> None:
        self.disclosure = await audit.begin_disclosure(
            actor=self.actor,
            action="ai.request",
            resource_type="ai_provider",
            resource_id=self.provider,
            summary=self.meta,
        )

    async def finish(self, error: AiError | None) -> None:
        if self.disclosure is None:  # The provider was not contacted.
            return
        await self.disclosure.record_outcome(
            audit.AuditOutcome.SUCCEEDED if error is None else audit.AuditOutcome.FAILED,
            {**self.meta, "error_code": error.category.value if error is not None else None},
        )

    async def finish_unexpected(self) -> None:
        if self.disclosure is not None:
            await self.disclosure.record_outcome(
                audit.AuditOutcome.FAILED, {**self.meta, "error_code": "internal_error"}
            )

    async def not_attempted(
        self, db: AsyncSession, exc: ai_settings_service.AiSettingsServiceError
    ) -> None:
        """The service refused before contacting the provider (e.g. not configured)."""
        await _record_failure(
            db,
            self.actor,
            "ai.request",
            "ai_provider",
            resource_id=self.provider,
            status=exc.status_code,
            error_code=exc.error.category.value,
            extra=self.meta,
        )


async def _current_default(db: AsyncSession) -> dict[str, object]:
    settings = await db.get(AiSettingsRecord, 1)
    if settings is None:
        return {"provider": None, "model": None}
    provider = settings.default_provider
    return {
        "provider": provider.value if isinstance(provider, AiProvider) else provider,
        "model": settings.default_model,
    }


# ── Routes ───────────────────────────────────────────────────────────


@router.get("", response_model=AiSettings)
async def get_ai_settings(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiSettings:
    return await ai_settings_service.get_settings(db)


@router.put("/providers/{provider}", response_model=AiProviderStatus)
async def save_provider_key(
    provider: AiProvider,
    data: AiProviderKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai_provider.key_save", "ai_provider", resource_id_param="provider")
    ),
) -> AiProviderStatus:
    result = await ai_settings_service.save_provider_key(db, provider, data.api_key)
    # The provider only: never the key or its hint.
    audit.record(
        db,
        actor=audit.actor_from_auth(_auth),
        action="ai_provider.key_save",
        resource_type="ai_provider",
        resource_id=provider.value,
        summary={"provider": provider.value},
    )
    await db.commit()
    return result


@router.delete("/providers/{provider}", status_code=204)
async def delete_provider(
    provider: AiProvider,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai_provider.delete", "ai_provider", resource_id_param="provider")
    ),
) -> Response:
    actor = audit.actor_from_auth(_auth)
    try:
        await ai_settings_service.delete_provider(db, provider)
    except ai_settings_service.AiSettingsServiceError as exc:
        await _record_failure(
            db,
            actor,
            "ai_provider.delete",
            "ai_provider",
            resource_id=provider.value,
            status=exc.status_code,
            error_code=exc.error.category.value,
            extra={"provider": provider.value},
        )
        return _error_response(exc)
    audit.record(
        db,
        actor=actor,
        action="ai_provider.delete",
        resource_type="ai_provider",
        resource_id=provider.value,
        summary={"provider": provider.value},
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/providers/{provider}/check", response_model=AiCheckResult)
async def check_provider(
    provider: AiProvider,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai.request", "ai_provider", resource_id_param="provider")
    ),
) -> AiCheckResult | JSONResponse:
    request = _AiRequestAudit(audit.actor_from_auth(_auth), "check", provider, None)
    try:
        result = await ai_settings_service.check_provider(
            db, provider, before_provider_call=request.begin
        )
        await db.commit()
    except ai_settings_service.AiSettingsServiceError as exc:
        await request.not_attempted(db, exc)
        return _error_response(exc)
    except Exception:
        await request.finish_unexpected()
        raise
    await request.finish(result.error)
    return result


@router.get("/providers/{provider}/models", response_model=AiModelList)
async def list_models(
    provider: AiProvider,
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai.request", "ai_provider", resource_id_param="provider")
    ),
) -> AiModelList | JSONResponse:
    # A fresh cached listing does not contact the provider: the service then
    # never calls ``request.begin`` and no ai.request event is recorded.
    request = _AiRequestAudit(audit.actor_from_auth(_auth), "list_models", provider, None)
    try:
        result = await ai_settings_service.list_models(
            db, provider, refresh=refresh, before_provider_call=request.begin
        )
        await db.commit()
    except ai_settings_service.AiSettingsServiceError as exc:
        await request.not_attempted(db, exc)
        return _error_response(exc)
    except Exception:
        await request.finish_unexpected()
        raise
    await request.finish(result.error)
    return result


@router.post("/providers/{provider}/inference-test", response_model=AiInferenceResult)
async def inference_test(
    provider: AiProvider,
    data: AiInferenceTestRequest,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai.request", "ai_provider", resource_id_param="provider")
    ),
) -> AiInferenceResult | JSONResponse:
    request = _AiRequestAudit(audit.actor_from_auth(_auth), "inference_test", provider, data.model)
    try:
        result = await ai_settings_service.inference_test(
            db,
            provider,
            data.model,
            actor=request.actor,
            retry_of=data.retry_of,
            before_provider_call=request.begin,
        )
        await db.commit()
    except ai_settings_service.AiSettingsServiceError as exc:
        await request.not_attempted(db, exc)
        return _error_response(exc)
    except Exception:
        await request.finish_unexpected()
        raise
    await request.finish(result.error)
    return result


@router.get("/providers/{provider}/inference-test/preview", response_model=AiInferencePreview)
async def inference_test_preview(
    provider: AiProvider,
    model: str = Query(min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiInferencePreview:
    """The exact prompt, limits and estimated maximum cost. No provider call."""
    return await ai_settings_service.inference_preview(db, provider, _model_param(model))


@router.put("/default", response_model=AiDefault)
async def set_default(
    data: AiDefaultUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(audit.audited_admin("ai_default.set", "ai_default")),
) -> AiDefault | JSONResponse:
    actor = audit.actor_from_auth(_auth)
    before = await _current_default(db)
    try:
        result = await ai_settings_service.set_default(db, data)
    except ai_settings_service.AiSettingsServiceError as exc:
        await _record_failure(
            db,
            actor,
            "ai_default.set",
            "ai_default",
            resource_id="default",
            status=exc.status_code,
            error_code=exc.error.category.value,
            extra={"provider": data.provider.value, "model": data.model},
        )
        return _error_response(exc)
    audit.record(
        db,
        actor=actor,
        action="ai_default.set",
        resource_type="ai_default",
        resource_id="default",
        summary={
            "before": before,
            "after": {"provider": result.provider.value, "model": result.model},
            "is_custom": result.is_custom,
        },
    )
    await db.commit()
    return result


@router.delete("/default", status_code=204)
async def clear_default(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(audit.audited_admin("ai_default.clear", "ai_default")),
) -> Response:
    before = await _current_default(db)
    await ai_settings_service.clear_default(db)
    audit.record(
        db,
        actor=audit.actor_from_auth(_auth),
        action="ai_default.clear",
        resource_type="ai_default",
        resource_id="default",
        summary={"before": before, "after": {"provider": None, "model": None}},
    )
    await db.commit()
    return Response(status_code=204)


# ── Usage accounting and guardrails (#17) ────────────────────────────


def _model_param(model: str) -> str:
    try:
        return validate_model_id(model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _month_param(month: str | None) -> tuple[int, int]:
    if month is None:
        return gateway.current_month()
    try:
        return parse_month(month)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="month must be YYYY-MM, 2000-01 to 9999-11"
        ) from None


def _policy_summary(policy: AiUsagePolicyOut) -> dict[str, object]:
    # "max_output", not "max_output_tokens": audit summaries drop keys containing "token".
    return {
        "monthly_budget_usd": policy.monthly_budget_usd,
        "max_output": policy.max_output_tokens,
        "max_concurrent_requests": policy.max_concurrent_requests,
        "max_requests_per_minute": policy.max_requests_per_minute,
        "unpriced_model_policy": policy.unpriced_model_policy,
    }


def _price_summary(price: AiModelPricingOut | None) -> dict[str, object] | None:
    if price is None:
        return None
    return {
        "input_usd_per_mtok": price.input_usd_per_mtok,
        "output_usd_per_mtok": price.output_usd_per_mtok,
    }


@router.get("/usage", response_model=AiUsageReport)
async def get_usage(
    month: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiUsageReport:
    year, month_number = _month_param(month)
    return await ai_settings_service.usage_report(db, year, month_number)


@router.get("/usage/records", response_model=AiUsageRecordPage)
async def get_usage_records(
    month: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    before: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiUsageRecordPage:
    year, month_number = _month_param(month)
    try:
        return await ai_settings_service.usage_records(
            db, year, month_number, limit=limit, before=before
        )
    except ai_settings_service.UsageCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/usage-policy", response_model=AiUsagePolicyOut)
async def get_usage_policy(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiUsagePolicyOut:
    return await ai_settings_service.get_usage_policy(db)


@router.put("/usage-policy", response_model=AiUsagePolicyOut)
async def update_usage_policy(
    data: AiUsagePolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(audit.audited_admin("ai_usage_policy.update", "ai_usage_policy")),
) -> AiUsagePolicyOut:
    before = await ai_settings_service.get_usage_policy(db)
    result = await ai_settings_service.update_usage_policy(db, data)
    audit.record(
        db,
        actor=audit.actor_from_auth(_auth),
        action="ai_usage_policy.update",
        resource_type="ai_usage_policy",
        resource_id="policy",
        summary={"before": _policy_summary(before), "after": _policy_summary(result)},
    )
    await db.commit()
    return result


@router.get("/pricing", response_model=AiModelPricingList)
async def list_pricing(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiModelPricingList:
    return await ai_settings_service.list_pricing(db)


@router.put("/pricing/{provider}/{model:path}", response_model=AiModelPricingOut)
async def set_pricing(
    provider: AiProvider,
    data: AiModelPricingUpdate,
    model: str = Path(),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai_pricing.update", "ai_pricing", resource_id_param="provider")
    ),
) -> AiModelPricingOut:
    model = _model_param(model)
    before = await ai_settings_service.get_pricing(db, provider, model)
    result = await ai_settings_service.set_pricing(db, provider, model, data)
    audit.record(
        db,
        actor=audit.actor_from_auth(_auth),
        action="ai_pricing.update",
        resource_type="ai_pricing",
        resource_id=provider.value,
        resource_label=model,
        summary={
            "provider": provider.value,
            "model": model,
            "before": _price_summary(before),
            "after": _price_summary(result),
        },
    )
    await db.commit()
    return result


@router.delete("/pricing/{provider}/{model:path}", status_code=204)
async def delete_pricing(
    provider: AiProvider,
    model: str = Path(),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("ai_pricing.delete", "ai_pricing", resource_id_param="provider")
    ),
) -> Response:
    actor = audit.actor_from_auth(_auth)
    model = _model_param(model)
    before = await ai_settings_service.get_pricing(db, provider, model)
    if before is None:
        await _record_failure(
            db,
            actor,
            "ai_pricing.delete",
            "ai_pricing",
            resource_id=provider.value,
            status=404,
            error_code="not_found",
            extra={"provider": provider.value, "model": model},
        )
        raise HTTPException(status_code=404, detail="No pricing for that model")
    await ai_settings_service.delete_pricing(db, provider, model)
    audit.record(
        db,
        actor=actor,
        action="ai_pricing.delete",
        resource_type="ai_pricing",
        resource_id=provider.value,
        resource_label=model,
        summary={"provider": provider.value, "model": model, "before": _price_summary(before)},
    )
    await db.commit()
    return Response(status_code=204)
