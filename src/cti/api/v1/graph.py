import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import CurrentUser
from cti.schemas.graph import GraphData
from cti.services.graph_service import build_graph

router = APIRouter()

VALID_ENTITY_TYPES = {"observable", "threat_actor", "campaign", "technique"}


@router.get("/{entity_type}/{entity_id}", response_model=GraphData)
async def get_graph(
    entity_type: str,
    entity_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    depth: int = Query(default=2, ge=1, le=3),
    include_threat_actors: bool = Query(default=True),
    include_campaigns: bool = Query(default=True),
    include_techniques: bool = Query(default=True),
) -> GraphData:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type. Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )

    return await build_graph(
        db,
        entity_type,
        entity_id,
        depth=depth,
        include_threat_actors=include_threat_actors,
        include_campaigns=include_campaigns,
        include_techniques=include_techniques,
    )
