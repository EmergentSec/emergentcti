"""FastAPI dependencies for request authentication."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Union

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.database import get_db
from cti.models.api_key import ApiKey
from cti.models.user import User, UserRole
from cti.services.auth_service import decode_access_token

# AuthSubject is either a User (web UI login) or ApiKey (programmatic access)
AuthSubject = Union[User, ApiKey]


async def get_current_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthSubject:
    """Dual-mode auth: JWT cookie first, then X-API-Key header fallback."""
    settings = get_settings()

    # 1. Try JWT cookie
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = decode_access_token(access_token, settings.JWT_SECRET_KEY.get_secret_value())
            user_id = payload["sub"]
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except (jwt.InvalidTokenError, KeyError):
            pass  # Fall through to API key check

    # 2. Try X-API-Key header (existing logic)
    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        api_key = result.scalar_one_or_none()
        if api_key is None or not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )
        api_key.last_used_at = datetime.now(timezone.utc)
        return api_key

    # 3. Neither present
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def require_admin(
    auth: AuthSubject = Depends(get_current_auth),
) -> AuthSubject:
    """Require admin role. API keys get admin-level access for backwards compatibility."""
    if isinstance(auth, ApiKey):
        return auth  # API keys get full access
    if auth.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return auth


# Backwards-compatible alias
verify_api_key = get_current_auth
