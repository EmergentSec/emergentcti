import logging
import uuid
from collections import deque

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.attack import AttackTechnique, ObservableTechnique
from cti.models.campaign import Campaign, campaign_observables
from cti.models.observable import Observable
from cti.models.relationship import ObservableRelationship
from cti.models.threat_actor import (
    ThreatActor,
    threat_actor_observables,
    threat_actor_techniques,
)
from cti.schemas.graph import GraphData, GraphEdge, GraphNode

logger = logging.getLogger(__name__)

MAX_NODES = 200


def _observable_node(obs: Observable) -> GraphNode:
    return GraphNode(
        id=str(obs.id),
        entity_type="observable",
        label=f"{obs.type.value}: {obs.value[:50]}",
        metadata={
            "observable_type": obs.type.value,
            "confidence": obs.confidence_score,
            "tlp": obs.tlp,
        },
    )


def _threat_actor_node(actor: ThreatActor) -> GraphNode:
    return GraphNode(
        id=str(actor.id),
        entity_type="threat_actor",
        label=actor.name,
        metadata={"aliases": actor.aliases or []},
    )


def _campaign_node(campaign: Campaign) -> GraphNode:
    return GraphNode(
        id=str(campaign.id),
        entity_type="campaign",
        label=campaign.name,
        metadata={"status": campaign.status},
    )


def _technique_node(tech: AttackTechnique) -> GraphNode:
    first_tactic = tech.tactics[0].name if tech.tactics else None
    return GraphNode(
        id=str(tech.id),
        entity_type="technique",
        label=f"{tech.external_id}: {tech.name}",
        metadata={"external_id": tech.external_id, "tactic": first_tactic},
    )


async def _expand_observable(
    db: AsyncSession,
    obs_id: uuid.UUID,
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    queue: deque[tuple[str, uuid.UUID, int]],
    current_depth: int,
    max_depth: int,
    include_threat_actors: bool,
    include_campaigns: bool,
    include_techniques: bool,
) -> None:
    """Expand an observable node by querying its relationships."""

    # 1. Observable relationships (both directions)
    result = await db.execute(
        select(ObservableRelationship).where(
            or_(
                ObservableRelationship.source_id == obs_id,
                ObservableRelationship.target_id == obs_id,
            )
        )
    )
    relationships = result.scalars().all()

    for rel in relationships:
        other_id = rel.target_id if rel.source_id == obs_id else rel.source_id
        other_id_str = str(other_id)

        if other_id_str not in nodes and len(nodes) < MAX_NODES:
            other_obs_result = await db.execute(
                select(Observable).where(Observable.id == other_id)
            )
            other_obs = other_obs_result.scalar_one_or_none()
            if other_obs:
                nodes[other_id_str] = _observable_node(other_obs)
                if current_depth < max_depth:
                    queue.append(("observable", other_id, current_depth + 1))

        edge = GraphEdge(
            source=str(rel.source_id),
            target=str(rel.target_id),
            relationship_type=rel.relationship_type,
            metadata={"confidence": rel.confidence},
        )
        # Avoid duplicate edges
        edge_key = (edge.source, edge.target, edge.relationship_type)
        existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
        if edge_key not in existing_keys:
            edges.append(edge)

    # 2. Threat actor associations
    if include_threat_actors:
        ta_result = await db.execute(
            select(ThreatActor)
            .join(
                threat_actor_observables,
                ThreatActor.id == threat_actor_observables.c.threat_actor_id,
            )
            .where(threat_actor_observables.c.observable_id == obs_id)
        )
        actors = ta_result.scalars().all()

        for actor in actors:
            actor_id_str = str(actor.id)
            if actor_id_str not in nodes and len(nodes) < MAX_NODES:
                nodes[actor_id_str] = _threat_actor_node(actor)
                if current_depth < max_depth:
                    queue.append(("threat_actor", actor.id, current_depth + 1))

            edge = GraphEdge(
                source=actor_id_str,
                target=str(obs_id),
                relationship_type="uses",
                metadata={},
            )
            edge_key = (edge.source, edge.target, edge.relationship_type)
            existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
            if edge_key not in existing_keys:
                edges.append(edge)

    # 3. Campaign associations
    if include_campaigns:
        camp_result = await db.execute(
            select(Campaign)
            .join(
                campaign_observables,
                Campaign.id == campaign_observables.c.campaign_id,
            )
            .where(campaign_observables.c.observable_id == obs_id)
        )
        campaigns = camp_result.scalars().all()

        for campaign in campaigns:
            camp_id_str = str(campaign.id)
            if camp_id_str not in nodes and len(nodes) < MAX_NODES:
                nodes[camp_id_str] = _campaign_node(campaign)
                if current_depth < max_depth:
                    queue.append(("campaign", campaign.id, current_depth + 1))

            edge = GraphEdge(
                source=camp_id_str,
                target=str(obs_id),
                relationship_type="involves",
                metadata={},
            )
            edge_key = (edge.source, edge.target, edge.relationship_type)
            existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
            if edge_key not in existing_keys:
                edges.append(edge)

    # 4. Technique associations
    if include_techniques:
        tech_result = await db.execute(
            select(AttackTechnique)
            .join(
                ObservableTechnique,
                AttackTechnique.id == ObservableTechnique.technique_id,
            )
            .where(ObservableTechnique.observable_id == obs_id)
        )
        techniques = tech_result.scalars().unique().all()

        for tech in techniques:
            tech_id_str = str(tech.id)
            if tech_id_str not in nodes and len(nodes) < MAX_NODES:
                nodes[tech_id_str] = _technique_node(tech)
                # Techniques are leaf nodes -- do not enqueue for further expansion

            edge = GraphEdge(
                source=str(obs_id),
                target=tech_id_str,
                relationship_type="observed-technique",
                metadata={},
            )
            edge_key = (edge.source, edge.target, edge.relationship_type)
            existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
            if edge_key not in existing_keys:
                edges.append(edge)


async def _expand_threat_actor(
    db: AsyncSession,
    actor_id: uuid.UUID,
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    queue: deque[tuple[str, uuid.UUID, int]],
    current_depth: int,
    max_depth: int,
    include_techniques: bool,
) -> None:
    """Expand a threat actor node by querying its observables and techniques."""

    # 1. Observables linked to this threat actor
    obs_result = await db.execute(
        select(Observable)
        .join(
            threat_actor_observables,
            Observable.id == threat_actor_observables.c.observable_id,
        )
        .where(threat_actor_observables.c.threat_actor_id == actor_id)
    )
    observables = obs_result.scalars().all()

    for obs in observables:
        obs_id_str = str(obs.id)
        if obs_id_str not in nodes and len(nodes) < MAX_NODES:
            nodes[obs_id_str] = _observable_node(obs)
            if current_depth < max_depth:
                queue.append(("observable", obs.id, current_depth + 1))

        edge = GraphEdge(
            source=str(actor_id),
            target=obs_id_str,
            relationship_type="uses",
            metadata={},
        )
        edge_key = (edge.source, edge.target, edge.relationship_type)
        existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
        if edge_key not in existing_keys:
            edges.append(edge)

    # 2. Techniques linked to this threat actor
    if include_techniques:
        tech_result = await db.execute(
            select(AttackTechnique)
            .join(
                threat_actor_techniques,
                AttackTechnique.id == threat_actor_techniques.c.technique_id,
            )
            .where(threat_actor_techniques.c.threat_actor_id == actor_id)
        )
        techniques = tech_result.scalars().unique().all()

        for tech in techniques:
            tech_id_str = str(tech.id)
            if tech_id_str not in nodes and len(nodes) < MAX_NODES:
                nodes[tech_id_str] = _technique_node(tech)

            edge = GraphEdge(
                source=str(actor_id),
                target=tech_id_str,
                relationship_type="employs",
                metadata={},
            )
            edge_key = (edge.source, edge.target, edge.relationship_type)
            existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
            if edge_key not in existing_keys:
                edges.append(edge)


async def _expand_campaign(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    queue: deque[tuple[str, uuid.UUID, int]],
    current_depth: int,
    max_depth: int,
) -> None:
    """Expand a campaign node by querying its observables."""

    obs_result = await db.execute(
        select(Observable)
        .join(
            campaign_observables,
            Observable.id == campaign_observables.c.observable_id,
        )
        .where(campaign_observables.c.campaign_id == campaign_id)
    )
    observables = obs_result.scalars().all()

    for obs in observables:
        obs_id_str = str(obs.id)
        if obs_id_str not in nodes and len(nodes) < MAX_NODES:
            nodes[obs_id_str] = _observable_node(obs)
            if current_depth < max_depth:
                queue.append(("observable", obs.id, current_depth + 1))

        edge = GraphEdge(
            source=str(campaign_id),
            target=obs_id_str,
            relationship_type="involves",
            metadata={},
        )
        edge_key = (edge.source, edge.target, edge.relationship_type)
        existing_keys = {(e.source, e.target, e.relationship_type) for e in edges}
        if edge_key not in existing_keys:
            edges.append(edge)


async def build_graph(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    depth: int = 2,
    include_threat_actors: bool = True,
    include_campaigns: bool = True,
    include_techniques: bool = True,
) -> GraphData:
    """Build a graph centered on a given entity using BFS expansion.

    Args:
        db: Async database session.
        entity_type: One of "observable", "threat_actor", "campaign", "technique".
        entity_id: UUID of the center entity.
        depth: Max BFS hops (1-3).
        include_threat_actors: Whether to include threat actor nodes.
        include_campaigns: Whether to include campaign nodes.
        include_techniques: Whether to include technique nodes.

    Returns:
        GraphData with nodes and edges.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # Load center entity
    entity_id_str = str(entity_id)

    if entity_type == "observable":
        result = await db.execute(select(Observable).where(Observable.id == entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            return GraphData(nodes=[], edges=[])
        nodes[entity_id_str] = _observable_node(entity)

    elif entity_type == "threat_actor":
        result = await db.execute(
            select(ThreatActor).where(ThreatActor.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            return GraphData(nodes=[], edges=[])
        nodes[entity_id_str] = _threat_actor_node(entity)

    elif entity_type == "campaign":
        result = await db.execute(select(Campaign).where(Campaign.id == entity_id))
        entity = result.scalar_one_or_none()
        if not entity:
            return GraphData(nodes=[], edges=[])
        nodes[entity_id_str] = _campaign_node(entity)

    elif entity_type == "technique":
        result = await db.execute(
            select(AttackTechnique).where(AttackTechnique.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            return GraphData(nodes=[], edges=[])
        nodes[entity_id_str] = _technique_node(entity)

    else:
        return GraphData(nodes=[], edges=[])

    # BFS queue: (entity_type, entity_id, current_depth)
    queue: deque[tuple[str, uuid.UUID, int]] = deque()
    queue.append((entity_type, entity_id, 1))
    visited: set[str] = set()

    while queue and len(nodes) < MAX_NODES:
        current_type, current_id, current_depth = queue.popleft()
        current_id_str = str(current_id)

        if current_id_str in visited:
            continue
        visited.add(current_id_str)

        if current_depth > depth:
            continue

        if current_type == "observable":
            await _expand_observable(
                db,
                current_id,
                nodes,
                edges,
                queue,
                current_depth,
                depth,
                include_threat_actors,
                include_campaigns,
                include_techniques,
            )
        elif current_type == "threat_actor":
            await _expand_threat_actor(
                db,
                current_id,
                nodes,
                edges,
                queue,
                current_depth,
                depth,
                include_techniques,
            )
        elif current_type == "campaign":
            await _expand_campaign(
                db,
                current_id,
                nodes,
                edges,
                queue,
                current_depth,
                depth,
            )
        # technique nodes are leaf nodes -- no further expansion

    # Filter edges to only include nodes present in the graph
    valid_ids = set(nodes.keys())
    filtered_edges = [
        e for e in edges if e.source in valid_ids and e.target in valid_ids
    ]

    return GraphData(nodes=list(nodes.values()), edges=filtered_edges)
