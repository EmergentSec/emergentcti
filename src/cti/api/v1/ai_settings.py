"""Admin-only AI provider configuration endpoints."""
# ruff: noqa: B008, TC001, TC002

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, require_admin
from cti.models.ai import AiProvider
from cti.schemas.ai import (
    AiCheckResult,
    AiDefault,
    AiDefaultUpdate,
    AiInferenceResult,
    AiInferenceTestRequest,
    AiModelList,
    AiProviderKeyUpdate,
    AiProviderStatus,
    AiSettings,
)
from cti.services import ai_settings_service

router = APIRouter()


def _error_response(error: ai_settings_service.AiSettingsServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=error.error.model_dump(mode="json"),
    )


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
    _auth: AuthSubject = Depends(require_admin),
) -> AiProviderStatus:
    return await ai_settings_service.save_provider_key(db, provider, data.api_key)


@router.delete("/providers/{provider}", status_code=204)
async def delete_provider(
    provider: AiProvider,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> Response:
    try:
        await ai_settings_service.delete_provider(db, provider)
    except ai_settings_service.AiSettingsServiceError as exc:
        return _error_response(exc)
    return Response(status_code=204)


@router.post("/providers/{provider}/check", response_model=AiCheckResult)
async def check_provider(
    provider: AiProvider,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiCheckResult | JSONResponse:
    try:
        return await ai_settings_service.check_provider(db, provider)
    except ai_settings_service.AiSettingsServiceError as exc:
        return _error_response(exc)


@router.get("/providers/{provider}/models", response_model=AiModelList)
async def list_models(
    provider: AiProvider,
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiModelList | JSONResponse:
    try:
        return await ai_settings_service.list_models(db, provider, refresh=refresh)
    except ai_settings_service.AiSettingsServiceError as exc:
        return _error_response(exc)


@router.post("/providers/{provider}/inference-test", response_model=AiInferenceResult)
async def inference_test(
    provider: AiProvider,
    data: AiInferenceTestRequest,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiInferenceResult | JSONResponse:
    try:
        return await ai_settings_service.inference_test(db, provider, data.model)
    except ai_settings_service.AiSettingsServiceError as exc:
        return _error_response(exc)


@router.put("/default", response_model=AiDefault)
async def set_default(
    data: AiDefaultUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AiDefault | JSONResponse:
    try:
        return await ai_settings_service.set_default(db, data)
    except ai_settings_service.AiSettingsServiceError as exc:
        return _error_response(exc)


@router.delete("/default", status_code=204)
async def clear_default(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> Response:
    await ai_settings_service.clear_default(db)
    return Response(status_code=204)
