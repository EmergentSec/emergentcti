"""Auth endpoints: login, refresh, logout, me."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.models.api_key import ApiKey
from cti.models.user import User
from cti.schemas.auth import AuthMeResponse, LoginRequest, TokenResponse
from cti.services.auth_service import (
    check_login_rate_limit,
    clear_login_rate_limit,
    create_access_token,
    create_refresh_token,
    record_failed_login,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)

router = APIRouter()

# Precomputed bcrypt hash for timing equalization when user doesn't exist.
# Cost factor $2b$12$ matches bcrypt.gensalt() default (12 rounds). Never matches any input.
_DUMMY_BCRYPT_HASH = "$2b$12$LJ3m4ys3Lg2VbEIDOlGNku4VR.edSKNnNR0M4PkGMGLnCMBVljX2G"


def _get_client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Rightmost entry is appended by our trusted proxy (nginx)
            return forwarded.split(",")[-1].strip()
    return request.client.host


def _set_access_cookie(response: Response, token: str, secure: bool, max_age: int) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api",
        max_age=max_age,
    )


def _set_refresh_cookie(response: Response, token: str, secure: bool, max_age: int) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/v1/auth/",
        max_age=max_age,
    )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username + password and issue JWT cookies."""
    settings = get_settings()
    client_ip = _get_client_ip(request)

    # Rate limit check BEFORE touching the DB for credentials
    await check_login_rate_limit(client_ip)

    # Look up user
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing-based user enumeration
    if user is not None:
        password_valid = await verify_password(body.password, user.password_hash)
    else:
        await verify_password(body.password, _DUMMY_BCRYPT_HASH)
        password_valid = False

    if user is None or not password_valid or not user.is_active:
        await record_failed_login(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Success — clear rate limit counter
    await clear_login_rate_limit(client_ip)

    # Issue tokens
    secret = settings.JWT_SECRET_KEY.get_secret_value()
    access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=secret,
        expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token = await create_refresh_token(
        db=db,
        user_id=user.id,
        expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    secure = settings.ENVIRONMENT != "development"
    _set_access_cookie(response, access_token, secure,
                       max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    _set_refresh_cookie(response, refresh_token, secure,
                        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return TokenResponse(id=user.id, username=user.username, role=user.role.value)


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Issue a new access token using a valid refresh token cookie."""
    settings = get_settings()

    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    db_token = await verify_refresh_token(db, raw_token)
    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.id == db_token.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Rotate: revoke old refresh token, issue new one
    db_token.revoked = True
    new_refresh = await create_refresh_token(
        db=db,
        user_id=user.id,
        expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )

    secret = settings.JWT_SECRET_KEY.get_secret_value()
    access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=secret,
        expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    await db.commit()

    secure = settings.ENVIRONMENT != "development"
    _set_access_cookie(response, access_token, secure,
                       max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    _set_refresh_cookie(response, new_refresh, secure,
                        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    return {"message": "Token refreshed"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke refresh token and clear auth cookies."""
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        await revoke_refresh_token(db, raw_token)
        await db.commit()

    # Clear both cookies — attributes must match the originals so browsers honour the deletion
    settings = get_settings()
    secure = settings.ENVIRONMENT != "development"
    response.set_cookie(key="access_token", value="", max_age=0, path="/api",
                        httponly=True, samesite="lax", secure=secure)
    response.set_cookie(key="refresh_token", value="", max_age=0, path="/api/v1/auth/",
                        httponly=True, samesite="lax", secure=secure)

    return {"message": "Logged out"}


@router.get("/me", response_model=AuthMeResponse, status_code=status.HTTP_200_OK)
async def me(
    auth: AuthSubject = Depends(get_current_auth),
) -> AuthMeResponse:
    """Return identity info for the current authenticated subject."""
    if isinstance(auth, User):
        return AuthMeResponse(
            type="user",
            id=auth.id,
            name=auth.username,
            role=auth.role.value,
        )
    # ApiKey
    return AuthMeResponse(
        type="api_key",
        id=auth.id,
        name=auth.name,
        role="admin",
    )
