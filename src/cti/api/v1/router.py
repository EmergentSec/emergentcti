"""Aggregate all v1 API routers."""

from fastapi import APIRouter

from cti.api.v1.export import router as export_router
from cti.api.v1.feeds import router as feeds_router
from cti.api.v1.health import router as health_router
from cti.api.v1.observables import router as observables_router
from cti.api.v1.settings import router as settings_router
from cti.api.v1.stats import router as stats_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(observables_router, prefix="/observables", tags=["observables"])
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(export_router, prefix="/export", tags=["export"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(stats_router, prefix="/stats", tags=["stats"])
