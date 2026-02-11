import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import CurrentUser
from cti.schemas.audit import AuditLogListResponse, AuditLogResponse
from cti.services import audit_service

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
) -> AuditLogListResponse:
    """List audit logs with filters and pagination.

    Non-admin users can only view their own audit logs.
    Admins can view all logs or filter by any user.
    """
    # Non-admin users can only see their own logs
    effective_user_id = user_id
    if user.role.value != "admin":
        effective_user_id = user.id

    items, total = await audit_service.list_audit_logs(
        db,
        page=page,
        size=size,
        user_id=effective_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=list[AuditLogResponse],
)
async def get_entity_audit_logs(
    entity_type: str,
    entity_id: str,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditLogResponse]:
    """Get audit logs for a specific entity."""
    items = await audit_service.get_entity_audit_logs(
        db, entity_type=entity_type, entity_id=entity_id, limit=limit
    )
    return [AuditLogResponse.model_validate(item) for item in items]
