"""Central authentication service: passwords, JWTs, refresh tokens, rate limiting."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.redis import get_redis
from cti.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)

# ── Password helpers ──────────────────────────────────────────────────────


async def hash_password(plain: str) -> str:
    """Hash a password with bcrypt using asyncio.to_thread() to avoid blocking."""
    hashed = await asyncio.to_thread(
        bcrypt.hashpw, plain.encode(), bcrypt.gensalt()
    )
    return hashed.decode()


async def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash using asyncio.to_thread()."""
    return await asyncio.to_thread(
        bcrypt.checkpw, plain.encode(), hashed.encode()
    )


# ── JWT helpers ───────────────────────────────────────────────────────────


def create_access_token(user_id: uuid.UUID, role: str, secret: str, expire_minutes: int) -> str:
    """Create a JWT access token.

    Payload: sub=str(user_id), role=role, type='access', exp, iat.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> dict:
    """Decode and verify a JWT access token.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


# ── Refresh token helpers ─────────────────────────────────────────────────


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID, expire_days: int) -> str:
    """Generate a random refresh token, store its SHA-256 hash in the DB, return the raw token."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=expire_days)
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()
    return raw


async def verify_refresh_token(db: AsyncSession, raw_token: str) -> RefreshToken | None:
    """Look up token by SHA-256 hash. Return RefreshToken if found, not expired, not revoked. Else None."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()
    if db_token is None:
        return None
    if db_token.revoked:
        # Reuse of a rotated token — treat as theft indicator (OAuth 2.0 BCP §4.13.2)
        logger.warning(
            "Revoked refresh token replayed — revoking all sessions for user %s",
            db_token.user_id,
        )
        await revoke_all_user_tokens(db, db_token.user_id)
        await db.flush()
        return None
    if db_token.expires_at < datetime.now(tz=timezone.utc):
        return None
    return db_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Mark a refresh token as revoked by SHA-256 hash lookup."""
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()
    if db_token is not None:
        db_token.revoked = True
        await db.flush()


async def revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke all active refresh tokens for a user (used on user delete)."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
    )
    tokens = result.scalars().all()
    for token in tokens:
        token.revoked = True
    if tokens:
        await db.flush()


# ── Rate limiting (login brute-force protection) ──────────────────────────

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_TTL_SECONDS = 900  # 15 minutes


def _rate_limit_key(ip: str) -> str:
    return f"login_fail:{ip}"


async def check_login_rate_limit(ip: str) -> None:
    """Check Redis counter. If >= 5 failed attempts in 15 min window, raise HTTPException 429."""
    redis = get_redis()
    key = _rate_limit_key(ip)
    count = await redis.get(key)
    if count is not None and int(count) >= _RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )


async def record_failed_login(ip: str) -> None:
    """Increment Redis counter for IP. Key: 'login_fail:{ip}', TTL: 900 seconds."""
    redis = get_redis()
    key = _rate_limit_key(ip)
    async with redis.pipeline() as pipe:
        pipe.incr(key)                                          # synchronous — buffers command
        pipe.expire(key, _RATE_LIMIT_TTL_SECONDS, nx=True)     # only set TTL on first attempt
        await pipe.execute()                                    # single async round-trip


async def clear_login_rate_limit(ip: str) -> None:
    """Delete Redis counter on successful login."""
    redis = get_redis()
    await redis.delete(_rate_limit_key(ip))


# ── Token maintenance ───────────────────────────────────────────────────


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """Delete expired refresh tokens. Revoked-but-unexpired rows are preserved
    so that reuse of a rotated token can still trigger theft detection."""
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now)
    )
    await db.commit()
    return result.rowcount
