"""Admin-only AI provider configuration endpoints."""
# ruff: noqa: B008, TC002

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
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
    AiInferenceResult,
    AiInferenceTestRequest,
    AiModelList,
    AiProviderKeyUpdate,
    AiProviderStatus,
    AiSettings,
)
from cti.services import ai_settings_service, audit

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
            db, provider, data.model, before_provider_call=request.begin
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
