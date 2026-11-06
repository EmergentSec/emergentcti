"""API key management, global configuration, and user management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.api.v1.auth import _set_refresh_cookie
from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.security import generate_api_key
from cti.models.api_key import ApiKey
from cti.models.user import User, UserRole
from cti.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from cti.schemas.user import PasswordChange, UserCreate, UserResponse, UserUpdate
from cti.services import audit
from cti.services.auth_service import (
    create_refresh_token,
    hash_password,
    revoke_all_user_tokens,
    verify_password,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────


async def _ensure_not_last_admin(db: AsyncSession, user: User) -> None:
    """Reject the operation if it would leave zero active admins."""
    if user.role != UserRole.admin or not user.is_active:
        return
    count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.role == UserRole.admin,
            User.is_active.is_(True),
            User.id != user.id,
        )
    )
    if count == 0:
        raise HTTPException(status_code=400, detail="Cannot remove the last active admin")


# ── Audit helpers ────────────────────────────────────────────────────

# Short reason codes for audited failures, keyed by the HTTPException detail.
_FAILURE_REASONS = {
    "API key not found": "not_found",
    "Cannot revoke your own API key": "self_revocation",
    "User not found": "not_found",
    "Username already taken": "username_taken",
    "Email already in use": "email_in_use",
    "Cannot deactivate your own account": "self_deactivation",
    "Cannot change your own role": "self_role_change",
    "Cannot remove the last active admin": "last_admin",
    "Cannot delete your own account": "self_deletion",
    "Cannot change another user's password": "not_permitted",
    "current_password required": "current_password_missing",
    "Current password is incorrect": "current_password_incorrect",
}


async def _record_failure(
    db: AsyncSession,
    actor: audit.Actor,
    action: str,
    resource_type: str,
    exc: HTTPException,
    *,
    resource_id: object = None,
    resource_label: str | None = None,
    outcome: audit.AuditOutcome = audit.AuditOutcome.FAILED,
    extra: dict[str, object] | None = None,
) -> None:
    """Record a failed or denied attempt. Roll back first: the request is doomed."""
    await db.rollback()
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=outcome,
        summary={
            **(extra or {}),
            "reason": _FAILURE_REASONS.get(str(exc.detail), "error"),
            "status": exc.status_code,
        },
        strict=False,
    )


def _before_after(before: object, after: object) -> dict[str, object]:
    return {"before": before, "after": after}


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
    _auth: AuthSubject = Depends(audit.audited_admin("api_key.create", "api_key")),
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
    # Identified by record id and name only: the raw key is returned once and never stored.
    audit.record(
        db,
        actor=audit.actor_from_auth(_auth),
        action="api_key.create",
        resource_type="api_key",
        resource_id=api_key.id,
        resource_label=api_key.name,
    )
    await db.commit()

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
    _auth: AuthSubject = Depends(
        audit.audited_admin("api_key.revoke", "api_key", resource_id_param="key_id")
    ),
) -> None:
    actor = audit.actor_from_auth(_auth)
    label: str | None = None
    try:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        label = key.name

        # Don't let users revoke their own key (only relevant when auth subject is an ApiKey)
        if isinstance(_auth, ApiKey) and key.id == _auth.id:
            raise HTTPException(status_code=400, detail="Cannot revoke your own API key")
    except HTTPException as exc:
        await _record_failure(
            db, actor, "api_key.revoke", "api_key", exc, resource_id=key_id, resource_label=label
        )
        raise

    was_active = key.is_active
    key.is_active = False
    audit.record(
        db,
        actor=actor,
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=key.id,
        resource_label=key.name,
        summary={"is_active": _before_after(was_active, False)},
    )
    await db.commit()


# ── Global Config ─────────────────────────────────────────────────────


# Read-only: config comes from environment variables. To change it, edit .env
# and restart. There is deliberately no PUT route (#36), so writes get a 405.
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
    _auth: AuthSubject = Depends(audit.audited_admin("user.create", "user")),
) -> UserResponse:
    actor = audit.actor_from_auth(_auth)
    try:
        existing = await db.execute(select(User).where(User.username == data.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")
        # Check email uniqueness if provided
        if data.email:
            existing_email = await db.execute(select(User).where(User.email == data.email))
            if existing_email.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already in use")
    except HTTPException as exc:
        await _record_failure(db, actor, "user.create", "user", exc, resource_label=data.username)
        raise
    password_hash = await hash_password(data.password)
    user = User(
        username=data.username,
        password_hash=password_hash,
        role=data.role,
        email=data.email,
    )
    db.add(user)
    await db.flush()
    audit.record(
        db,
        actor=actor,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.username,
        summary={"role": user.role, "is_active": user.is_active},
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("user.update", "user", resource_id_param="user_id")
    ),
) -> UserResponse:
    actor = audit.actor_from_auth(_auth)
    label: str | None = None
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        label = user.username
        before = {"role": user.role, "is_active": user.is_active, "email": user.email}

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
    except HTTPException as exc:
        await _record_failure(
            db, actor, "user.update", "user", exc, resource_id=user_id, resource_label=label
        )
        raise

    after = {"role": user.role, "is_active": user.is_active, "email": user.email}
    changed = sorted(name for name in before if before[name] != after[name])
    # Field names only; role and is_active also as before/after, never the email.
    summary: dict[str, object] = {"changed_fields": changed}
    for name in ("role", "is_active"):
        if name in changed:
            summary[name] = _before_after(before[name], after[name])
    audit.record(
        db,
        actor=actor,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.username,
        summary=summary,
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(
        audit.audited_admin("user.delete", "user", resource_id_param="user_id")
    ),
) -> None:
    actor = audit.actor_from_auth(_auth)
    label: str | None = None
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        label = user.username

        # Cannot delete yourself
        if isinstance(_auth, User) and user.id == _auth.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")

        await _ensure_not_last_admin(db, user)
    except HTTPException as exc:
        await _record_failure(
            db, actor, "user.delete", "user", exc, resource_id=user_id, resource_label=label
        )
        raise
    # The username snapshot keeps the history readable after the row is gone.
    audit.record(
        db,
        actor=actor,
        action="user.delete",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.username,
        summary={"role": user.role, "is_active": user.is_active},
    )
    await revoke_all_user_tokens(db, user.id)
    await db.delete(user)
    await db.commit()


@router.put("/users/{user_id}/password", status_code=204)
async def change_user_password(
    user_id: uuid.UUID,
    data: PasswordChange,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> None:
    actor = audit.actor_from_auth(_auth)
    label: str | None = None
    is_self = isinstance(_auth, User) and _auth.id == user_id
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        label = user.username

        # API keys are treated as admin-equivalent for backwards compatibility.
        # Any valid API key can change any user's password without providing
        # the current password.
        is_admin = isinstance(_auth, ApiKey) or (
            isinstance(_auth, User) and _auth.role == UserRole.admin
        )

        if not is_admin and not is_self:
            raise HTTPException(status_code=403, detail="Cannot change another user's password")

        # Changing your own password always requires the current one, admins included.
        if is_self:
            if not data.current_password:
                raise HTTPException(status_code=400, detail="current_password required")
            if not await verify_password(data.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
    except HTTPException as exc:
        await _record_failure(
            db,
            actor,
            "user.password_change",
            "user",
            exc,
            resource_id=user_id,
            resource_label=label,
            outcome=(
                audit.AuditOutcome.DENIED if exc.status_code == 403 else audit.AuditOutcome.FAILED
            ),
            extra={"self_service": is_self},
        )
        raise

    # Never the password or its hash: only who changed whose password.
    audit.record(
        db,
        actor=actor,
        action="user.password_change",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.username,
        summary={"self_service": is_self},
    )
    user.password_hash = await hash_password(data.new_password)
    # Revoke existing sessions so other devices must log in with the new password.
    await revoke_all_user_tokens(db, user.id)
    if is_self:
        # Keep the session that made the change signed in: issue it a fresh
        # refresh token (the cookie is not sent to this path, so it cannot be spared).
        settings = get_settings()
        refresh_token = await create_refresh_token(
            db=db,
            user_id=user.id,
            expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        )
        _set_refresh_cookie(
            response,
            refresh_token,
            secure=settings.ENVIRONMENT != "development",
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )
    await db.commit()
