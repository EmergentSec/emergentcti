from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.security import decode_token
from cti.models.user import User, UserRole

ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.readonly: 0,
    UserRole.analyst: 1,
    UserRole.admin: 2,
}


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try Bearer JWT first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user

    # Fall back to X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        result = await db.execute(select(User).where(User.api_key == api_key))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(min_role: UserRole):  # noqa: ANN201
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if ROLE_HIERARCHY[current_user.role] < ROLE_HIERARCHY[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} role or higher",
            )
        return current_user

    return role_checker


CurrentUser = Annotated[User, Depends(get_current_user)]
AnalystUser = Annotated[User, Depends(require_role(UserRole.analyst))]
AdminUser = Annotated[User, Depends(require_role(UserRole.admin))]
