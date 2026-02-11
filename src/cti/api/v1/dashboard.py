from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import CurrentUser
from cti.schemas.dashboard import DashboardStats
from cti.services import dashboard_service

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    return await dashboard_service.get_dashboard_stats(db)


@router.get("/trend")
async def observable_trend(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> list[dict]:
    """Daily observable creation counts for the last N days."""
    return await dashboard_service.get_observable_trend(db, days=days)


@router.get("/tlp-distribution")
async def tlp_distribution(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Count of observables per TLP level."""
    return await dashboard_service.get_tlp_distribution(db)


@router.get("/top-tags")
async def top_tags(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=15, ge=1, le=100),
) -> list[dict]:
    """Most frequently used tags."""
    return await dashboard_service.get_top_tags(db, limit=limit)
