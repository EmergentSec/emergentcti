"""FastAPI dependencies for request authentication."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.models.api_key import ApiKey


async def verify_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate the ``X-API-Key`` header and return the matching :class:`ApiKey` record.

    On success the key's ``last_used_at`` timestamp is updated (committed by
    the ``get_db`` dependency on normal exit).

    Raises:
        HTTPException 401: If the header is missing, the key is unknown, or
            the key has been deactivated.
    """
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash),
    )
    api_key = result.scalar_one_or_none()

    if api_key is None or not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # Touch last-used timestamp (will be committed by get_db)
    api_key.last_used_at = datetime.now(timezone.utc)

    return api_key
