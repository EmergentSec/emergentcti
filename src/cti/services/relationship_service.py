import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cti.models.observable import Observable
from cti.models.relationship import ObservableRelationship
from cti.schemas.relationship import RelationshipCreate, RelationshipUpdate


async def create_relationship(
    db: AsyncSession,
    source_id: uuid.UUID,
    data: RelationshipCreate,
    user_id: uuid.UUID,
) -> ObservableRelationship:
    """Create a new relationship between two observables."""
    # Validate source != target
    if source_id == data.target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target observables must be different",
        )

    # Validate source observable exists
    source_result = await db.execute(
        select(Observable).where(Observable.id == source_id)
    )
    if not source_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source observable not found",
        )

    # Validate target observable exists
    target_result = await db.execute(
        select(Observable).where(Observable.id == data.target_id)
    )
    if not target_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target observable not found",
        )

    rel = ObservableRelationship(
        source_id=source_id,
        target_id=data.target_id,
        relationship_type=data.relationship_type,
        confidence=data.confidence,
        metadata_=data.metadata,
        created_by=user_id,
    )
    db.add(rel)
    await db.flush()
    await db.refresh(rel, ["source", "target"])
    return rel


async def list_relationships(
    db: AsyncSession,
    observable_id: uuid.UUID,
    direction: str = "both",
) -> list[ObservableRelationship]:
    """List relationships for an observable, filtered by direction."""
    query = select(ObservableRelationship).options(
        joinedload(ObservableRelationship.source),
        joinedload(ObservableRelationship.target),
    )

    if direction == "outgoing":
        query = query.where(ObservableRelationship.source_id == observable_id)
    elif direction == "incoming":
        query = query.where(ObservableRelationship.target_id == observable_id)
    else:
        query = query.where(
            or_(
                ObservableRelationship.source_id == observable_id,
                ObservableRelationship.target_id == observable_id,
            )
        )

    query = query.order_by(ObservableRelationship.created_at.desc())
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def get_relationship(
    db: AsyncSession, relationship_id: uuid.UUID
) -> ObservableRelationship | None:
    """Get a single relationship by ID."""
    result = await db.execute(
        select(ObservableRelationship)
        .options(
            joinedload(ObservableRelationship.source),
            joinedload(ObservableRelationship.target),
        )
        .where(ObservableRelationship.id == relationship_id)
    )
    return result.unique().scalar_one_or_none()


async def update_relationship(
    db: AsyncSession,
    relationship_id: uuid.UUID,
    data: RelationshipUpdate,
) -> ObservableRelationship | None:
    """Update an existing relationship."""
    rel = await get_relationship(db, relationship_id)
    if not rel:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata":
            rel.metadata_ = value
        else:
            setattr(rel, field, value)

    await db.flush()
    await db.refresh(rel, ["source", "target"])
    return rel


async def delete_relationship(
    db: AsyncSession, relationship_id: uuid.UUID
) -> bool:
    """Delete a relationship by ID."""
    result = await db.execute(
        select(ObservableRelationship).where(
            ObservableRelationship.id == relationship_id
        )
    )
    rel = result.scalar_one_or_none()
    if not rel:
        return False
    await db.delete(rel)
    await db.flush()
    return True


async def get_relationship_graph(
    db: AsyncSession,
    observable_id: uuid.UUID,
    depth: int = 2,
) -> dict:
    """Build a relationship graph via BFS traversal from a starting observable.

    Returns a dict with 'nodes' and 'edges' lists suitable for graph rendering.
    Depth is capped at 3 to prevent excessive queries.
    """
    depth = min(depth, 3)

    # Validate the starting observable exists
    start_result = await db.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    start_obs = start_result.scalar_one_or_none()
    if not start_obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observable not found",
        )

    # BFS traversal
    visited: set[uuid.UUID] = {observable_id}
    frontier: set[uuid.UUID] = {observable_id}
    nodes: dict[uuid.UUID, dict] = {
        observable_id: {
            "id": str(observable_id),
            "type": (
                start_obs.type.value
                if hasattr(start_obs.type, "value")
                else str(start_obs.type)
            ),
            "value": start_obs.value,
            "confidence_score": start_obs.confidence_score,
        }
    }
    edges: list[dict] = []

    for _ in range(depth):
        if not frontier:
            break

        frontier_list = list(frontier)
        query = (
            select(ObservableRelationship)
            .options(
                joinedload(ObservableRelationship.source),
                joinedload(ObservableRelationship.target),
            )
            .where(
                or_(
                    ObservableRelationship.source_id.in_(frontier_list),
                    ObservableRelationship.target_id.in_(frontier_list),
                )
            )
        )
        result = await db.execute(query)
        rels = result.unique().scalars().all()

        next_frontier: set[uuid.UUID] = set()

        for rel in rels:
            # Add edge
            edges.append(
                {
                    "id": str(rel.id),
                    "source": str(rel.source_id),
                    "target": str(rel.target_id),
                    "relationship_type": rel.relationship_type,
                    "confidence": rel.confidence,
                }
            )

            # Process source node
            if rel.source_id not in visited:
                visited.add(rel.source_id)
                next_frontier.add(rel.source_id)
                if rel.source:
                    nodes[rel.source_id] = {
                        "id": str(rel.source_id),
                        "type": (
                            rel.source.type.value
                            if hasattr(rel.source.type, "value")
                            else str(rel.source.type)
                        ),
                        "value": rel.source.value,
                        "confidence_score": rel.source.confidence_score,
                    }

            # Process target node
            if rel.target_id not in visited:
                visited.add(rel.target_id)
                next_frontier.add(rel.target_id)
                if rel.target:
                    nodes[rel.target_id] = {
                        "id": str(rel.target_id),
                        "type": (
                            rel.target.type.value
                            if hasattr(rel.target.type, "value")
                            else str(rel.target.type)
                        ),
                        "value": rel.target.value,
                        "confidence_score": rel.target.confidence_score,
                    }

        frontier = next_frontier

    # Deduplicate edges by id
    seen_edge_ids: set[str] = set()
    unique_edges: list[dict] = []
    for edge in edges:
        if edge["id"] not in seen_edge_ids:
            seen_edge_ids.add(edge["id"])
            unique_edges.append(edge)

    return {
        "nodes": list(nodes.values()),
        "edges": unique_edges,
    }
