import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Log an audit event."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_audit_logs(
    db: AsyncSession,
    page: int = 1,
    size: int = 50,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
) -> tuple[list[AuditLog], int]:
    """List audit logs with filters and pagination."""
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    if entity_type is not None:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
        count_query = count_query.where(AuditLog.entity_id == entity_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    total = await db.scalar(count_query) or 0

    offset = (page - 1) * size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def get_entity_audit_logs(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> list[AuditLog]:
    """Get audit logs for a specific entity."""
    query = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
