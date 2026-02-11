import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.user import User, UserRole


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, role: str | None = None, is_active: bool | None = None
) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if role is not None:
        user.role = UserRole(role)
    if is_active is not None:
        user.is_active = is_active
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    await db.delete(user)
    await db.flush()
    return True


async def bulk_update_users(
    db: AsyncSession, ids: list[uuid.UUID], role: str | None = None, is_active: bool | None = None
) -> int:
    values = {}
    if role is not None:
        values["role"] = UserRole(role)
    if is_active is not None:
        values["is_active"] = is_active
    if not values:
        return 0
    result = await db.execute(
        update(User).where(User.id.in_(ids)).values(**values)
    )
    await db.flush()
    return result.rowcount


async def bulk_delete_users(db: AsyncSession, ids: list[uuid.UUID]) -> int:
    result = await db.execute(delete(User).where(User.id.in_(ids)))
    await db.flush()
    return result.rowcount
