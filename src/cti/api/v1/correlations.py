import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AnalystUser, CurrentUser
from cti.schemas.correlation import (
    CorrelationEventListResponse,
    CorrelationEventResponse,
    CorrelationRuleCreate,
    CorrelationRuleResponse,
    CorrelationRuleUpdate,
)
from cti.services import correlation_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Correlation Rules
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[CorrelationRuleResponse])
async def list_correlation_rules(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[CorrelationRuleResponse]:
    """List all correlation rules."""
    rules = await correlation_service.list_rules(db)
    return [CorrelationRuleResponse.model_validate(r) for r in rules]


@router.post(
    "/rules", response_model=CorrelationRuleResponse, status_code=status.HTTP_201_CREATED
)
async def create_correlation_rule(
    data: CorrelationRuleCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRuleResponse:
    """Create a new correlation rule."""
    rule = await correlation_service.create_rule(db, data, user_id=user.id)
    return CorrelationRuleResponse.model_validate(rule)


@router.get("/rules/{rule_id}", response_model=CorrelationRuleResponse)
async def get_correlation_rule(
    rule_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRuleResponse:
    """Get a single correlation rule."""
    rule = await correlation_service.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correlation rule not found"
        )
    return CorrelationRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=CorrelationRuleResponse)
async def update_correlation_rule(
    rule_id: uuid.UUID,
    data: CorrelationRuleUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRuleResponse:
    """Update an existing correlation rule."""
    rule = await correlation_service.update_rule(db, rule_id, data)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correlation rule not found"
        )
    return CorrelationRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correlation_rule(
    rule_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a correlation rule."""
    deleted = await correlation_service.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correlation rule not found"
        )


# ---------------------------------------------------------------------------
# Correlation Events
# ---------------------------------------------------------------------------


@router.get("/events", response_model=CorrelationEventListResponse)
async def list_correlation_events(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    rule_id: uuid.UUID | None = None,
) -> CorrelationEventListResponse:
    """List correlation events with pagination."""
    items, total = await correlation_service.list_events(
        db, page=page, size=size, rule_id=rule_id
    )
    return CorrelationEventListResponse(
        items=[CorrelationEventResponse(**item) for item in items],
        total=total,
        page=page,
        size=size,
    )


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_correlations(
    _user: AnalystUser,
    observable_ids: list[uuid.UUID],
    feed_id: uuid.UUID | None = None,
) -> dict:
    """Manually trigger correlation evaluation for a set of observables.

    Dispatches a background Celery task.
    """
    from cti.worker import run_correlations_task

    run_correlations_task.delay(
        [str(oid) for oid in observable_ids],
        feed_id=str(feed_id) if feed_id else None,
    )
    return {
        "status": "accepted",
        "observable_count": len(observable_ids),
    }
