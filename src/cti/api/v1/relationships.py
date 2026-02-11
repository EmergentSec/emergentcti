import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.relationship import (
    GraphResponse,
    RelationshipCreate,
    RelationshipResponse,
    RelationshipUpdate,
)
from cti.services import relationship_service

router = APIRouter()


@router.get(
    "/observables/{observable_id}/relationships",
    response_model=list[RelationshipResponse],
)
async def list_observable_relationships(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    direction: str = Query(default="both", pattern="^(outgoing|incoming|both)$"),
) -> list[RelationshipResponse]:
    """List all relationships for an observable."""
    rels = await relationship_service.list_relationships(
        db, observable_id, direction=direction
    )
    return [RelationshipResponse.model_validate(r) for r in rels]


@router.post(
    "/observables/{observable_id}/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_observable_relationship(
    observable_id: uuid.UUID,
    data: RelationshipCreate,
    analyst: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> RelationshipResponse:
    """Create a new relationship from this observable to another."""
    rel = await relationship_service.create_relationship(
        db, source_id=observable_id, data=data, user_id=analyst.id
    )
    return RelationshipResponse.model_validate(rel)


@router.get(
    "/observables/{observable_id}/graph",
    response_model=GraphResponse,
)
async def get_observable_graph(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    depth: int = Query(default=2, ge=1, le=3),
) -> GraphResponse:
    """Get a relationship graph for an observable via BFS traversal."""
    graph = await relationship_service.get_relationship_graph(
        db, observable_id, depth=depth
    )
    return GraphResponse(**graph)


@router.put(
    "/relationships/{relationship_id}",
    response_model=RelationshipResponse,
)
async def update_relationship(
    relationship_id: uuid.UUID,
    data: RelationshipUpdate,
    _analyst: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> RelationshipResponse:
    """Update an existing relationship."""
    rel = await relationship_service.update_relationship(db, relationship_id, data)
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )
    return RelationshipResponse.model_validate(rel)


@router.delete(
    "/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_relationship(
    relationship_id: uuid.UUID,
    _admin: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a relationship (admin only)."""
    deleted = await relationship_service.delete_relationship(db, relationship_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )
