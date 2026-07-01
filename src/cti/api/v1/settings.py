"""API key management, global configuration, and user management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.security import generate_api_key
from cti.models.api_key import ApiKey
from cti.models.user import User, UserRole
from cti.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from cti.schemas.user import PasswordChange, UserCreate, UserResponse, UserUpdate
from cti.services.auth_service import hash_password, revoke_all_user_tokens, verify_password

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────


async def _ensure_not_last_admin(db: AsyncSession, user: User) -> None:
    """Reject the operation if it would leave zero active admins."""
    if user.role != UserRole.admin or not user.is_active:
        return
    count = await db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.admin,
            User.is_active.is_(True),
            User.id != user.id,
        )
    )
    if count == 0:
        raise HTTPException(status_code=400, detail="Cannot remove the last active admin")


# ── API Key Management ────────────────────────────────────────────────


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
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
    _auth: AuthSubject = Depends(require_admin),
) -> ApiKeyCreateResponse:
    raw_key, key_hash, key_prefix = generate_api_key()
    created_by_id = _auth.id if isinstance(_auth, User) else None

    api_key = ApiKey(
        name=data.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        description=data.description,
        created_by=created_by_id,
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
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Don't let users revoke their own key (only relevant when auth subject is an ApiKey)
    if isinstance(_auth, ApiKey) and key.id == _auth.id:
        raise HTTPException(status_code=400, detail="Cannot revoke your own API key")

    key.is_active = False
    await db.flush()


# ── Global Config ─────────────────────────────────────────────────────


@router.get("/config")
async def get_config(
    _auth: AuthSubject = Depends(get_current_auth),
) -> dict:
    settings = get_settings()
    return {
        "confidence_decay_enabled": settings.CONFIDENCE_DECAY_ENABLED,
        "confidence_decay_days": settings.CONFIDENCE_DECAY_DAYS,
        "confidence_decay_rate": settings.CONFIDENCE_DECAY_RATE,
        "confidence_decay_floor": settings.CONFIDENCE_DECAY_FLOOR,
        "confidence_decay_interval_hours": settings.CONFIDENCE_DECAY_INTERVAL_HOURS,
        "instance_name": settings.INSTANCE_NAME,
        "observable_retention_days": settings.OBSERVABLE_RETENTION_DAYS,
        "default_export_format": settings.DEFAULT_EXPORT_FORMAT,
    }


@router.put("/config")
async def update_config(
    data: dict,
    _auth: AuthSubject = Depends(require_admin),
) -> dict:
    # Config is environment-driven; this endpoint is a read-only view for now.
    # To update, modify .env and restart. This returns current values.
    raise HTTPException(
        status_code=501,
        detail="Config updates require modifying environment variables and restarting. Use GET to view current config.",
    )


# ── User Management ───────────────────────────────────────────────────


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> UserResponse:
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    # Check email uniqueness if provided
    if data.email:
        existing_email = await db.execute(select(User).where(User.email == data.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
    password_hash = await hash_password(data.password)
    user = User(
        username=data.username,
        password_hash=password_hash,
        role=data.role,
        email=data.email,
    )
    db.add(user)
    await db.flush()
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot deactivate yourself
    if data.is_active is False and isinstance(_auth, User) and user.id == _auth.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    if data.role is not None and data.role != UserRole.admin:
        if isinstance(_auth, User) and user.id == _auth.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Last-admin protection: block demotion or deactivation of the last active admin
    if data.role is not None and data.role != UserRole.admin:
        await _ensure_not_last_admin(db, user)
    if data.is_active is False:
        await _ensure_not_last_admin(db, user)

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.email is not None:
        if data.email:  # non-empty string
            existing_email = await db.execute(
                select(User).where(User.email == data.email, User.id != user_id)
            )
            if existing_email.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email

    await db.flush()
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cannot delete yourself
    if isinstance(_auth, User) and user.id == _auth.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    await _ensure_not_last_admin(db, user)
    await revoke_all_user_tokens(db, user.id)
    await db.delete(user)
    await db.flush()


@router.put("/users/{user_id}/password", status_code=204)
async def change_user_password(
    user_id: uuid.UUID,
    data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # API keys are treated as admin-equivalent for backwards compatibility.
    # Any valid API key can change any user's password without providing
    # the current password.
    is_admin = isinstance(_auth, ApiKey) or (isinstance(_auth, User) and _auth.role == UserRole.admin)
    is_self = isinstance(_auth, User) and _auth.id == user_id

    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Cannot change another user's password")

    if not is_admin and is_self:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="current_password required")
        if not await verify_password(data.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = await hash_password(data.new_password)
    # Always revoke sessions — forces re-login with the new password
    await revoke_all_user_tokens(db, user.id)
    await db.flush()
