from fastapi import APIRouter

from cti.api.v1.alerts import router as alerts_router
from cti.api.v1.attack import router as attack_router
from cti.api.v1.audit import router as audit_router
from cti.api.v1.auth import router as auth_router
from cti.api.v1.campaigns import router as campaigns_router
from cti.api.v1.correlations import router as correlations_router
from cti.api.v1.dashboard import router as dashboard_router
from cti.api.v1.enrichment import router as enrichment_router
from cti.api.v1.export import router as export_router
from cti.api.v1.feeds import router as feeds_router
from cti.api.v1.graph import router as graph_router
from cti.api.v1.import_ import router as import_router
from cti.api.v1.observables import router as observables_router
from cti.api.v1.relationships import router as relationships_router
from cti.api.v1.reports import router as reports_router
from cti.api.v1.saved_searches import router as saved_searches_router
from cti.api.v1.search import router as search_router
from cti.api.v1.sso import router as sso_router
from cti.api.v1.threat_actors import router as threat_actors_router
from cti.api.v1.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(observables_router, prefix="/observables", tags=["observables"])
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(relationships_router, tags=["relationships"])
api_router.include_router(sso_router, prefix="/sso", tags=["sso"])
api_router.include_router(attack_router, prefix="/attack", tags=["attack"])
api_router.include_router(
    saved_searches_router, prefix="/saved-searches", tags=["saved-searches"]
)
api_router.include_router(enrichment_router, prefix="/enrichment", tags=["enrichment"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(export_router, prefix="/export", tags=["export"])
api_router.include_router(import_router, prefix="/import", tags=["import"])
api_router.include_router(
    threat_actors_router, prefix="/threat-actors", tags=["threat-actors"]
)
api_router.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(
    correlations_router, prefix="/correlations", tags=["correlations"]
)
api_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
