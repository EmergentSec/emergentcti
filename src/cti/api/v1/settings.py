"""API key management and global configuration endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import verify_api_key
from cti.core.security import generate_api_key
from cti.models.api_key import ApiKey
from cti.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse

router = APIRouter()


# ── API Key Management ────────────────────────────────────────────────


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
) -> list[ApiKeyResponse]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.is_active.is_(True)).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [ApiKeyResponse.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key_endpoint(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
) -> ApiKeyCreateResponse:
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        name=data.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        description=data.description,
    )
    db.add(api_key)
    await db.flush()

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        description=api_key.description,
        key=raw_key,
    )


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _api_key: ApiKey = Depends(verify_api_key),
) -> None:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Don't let users revoke their own key
    if key.id == _api_key.id:
        raise HTTPException(status_code=400, detail="Cannot revoke your own API key")

    key.is_active = False
    await db.flush()


# ── Global Config ─────────────────────────────────────────────────────


@router.get("/config")
async def get_config(
    _api_key: ApiKey = Depends(verify_api_key),
) -> dict:
    settings = get_settings()
    return {
        "confidence_decay_enabled": settings.CONFIDENCE_DECAY_ENABLED,
        "confidence_decay_days": settings.CONFIDENCE_DECAY_DAYS,
        "confidence_decay_rate": settings.CONFIDENCE_DECAY_RATE,
        "confidence_decay_floor": settings.CONFIDENCE_DECAY_FLOOR,
        "confidence_decay_interval_hours": settings.CONFIDENCE_DECAY_INTERVAL_HOURS,
    }


@router.put("/config")
async def update_config(
    data: dict,
    _api_key: ApiKey = Depends(verify_api_key),
) -> dict:
    # Config is environment-driven; this endpoint is a read-only view for now.
    # To update, modify .env and restart. This returns current values.
    raise HTTPException(
        status_code=501,
        detail="Config updates require modifying environment variables and restarting. Use GET to view current config.",
    )
