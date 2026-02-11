import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AnalystUser, CurrentUser
from cti.schemas.alert import (
    AlertEventListResponse,
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from cti.services import alert_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[AlertRuleResponse]:
    """List all alert rules."""
    rules = await alert_service.list_alert_rules(db)
    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    data: AlertRuleCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> AlertRuleResponse:
    """Create a new alert rule."""
    rule = await alert_service.create_alert_rule(db, data, user_id=user.id)
    return AlertRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: uuid.UUID,
    data: AlertRuleUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> AlertRuleResponse:
    """Update an existing alert rule."""
    rule = await alert_service.update_alert_rule(db, rule_id, data)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found"
        )
    return AlertRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an alert rule."""
    deleted = await alert_service.delete_alert_rule(db, rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found"
        )


# ---------------------------------------------------------------------------
# Alert Events
# ---------------------------------------------------------------------------


@router.get("/events", response_model=AlertEventListResponse)
async def list_alert_events(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    rule_id: uuid.UUID | None = None,
) -> AlertEventListResponse:
    """List alert events with pagination."""
    items, total = await alert_service.list_alert_events(
        db, page=page, size=size, rule_id=rule_id
    )
    return AlertEventListResponse(
        items=[AlertEventResponse(**item) for item in items],
        total=total,
        page=page,
        size=size,
    )
