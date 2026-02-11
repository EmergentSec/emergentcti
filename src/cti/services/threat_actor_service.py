import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.attack import AttackTechnique
from cti.models.observable import Observable
from cti.models.threat_actor import (
    ThreatActor,
    threat_actor_observables,
    threat_actor_techniques,
)
from cti.schemas.threat_actor import ThreatActorCreate, ThreatActorUpdate


async def create_threat_actor(
    db: AsyncSession,
    data: ThreatActorCreate,
    created_by: uuid.UUID | None = None,
) -> ThreatActor:
    actor = ThreatActor(
        name=data.name,
        aliases=data.aliases,
        description=data.description,
        motivation=data.motivation,
        sophistication=data.sophistication,
        country=data.country,
        first_seen=data.first_seen,
        last_seen=data.last_seen,
        tlp=data.tlp,
        external_references=data.external_references,
        created_by=created_by,
    )
    db.add(actor)
    await db.flush()
    await db.refresh(actor, ["observables", "techniques"])
    return actor


async def get_threat_actor(
    db: AsyncSession, actor_id: uuid.UUID
) -> ThreatActor | None:
    result = await db.execute(
        select(ThreatActor).where(ThreatActor.id == actor_id)
    )
    return result.scalar_one_or_none()


async def list_threat_actors(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    name_search: str | None = None,
    country: str | None = None,
    motivation: str | None = None,
) -> tuple[list[ThreatActor], int]:
    query = select(ThreatActor)
    count_query = select(func.count(ThreatActor.id))

    if name_search:
        query = query.where(ThreatActor.name.ilike(f"%{name_search}%"))
        count_query = count_query.where(ThreatActor.name.ilike(f"%{name_search}%"))

    if country:
        query = query.where(ThreatActor.country == country)
        count_query = count_query.where(ThreatActor.country == country)

    if motivation:
        query = query.where(ThreatActor.motivation == motivation)
        count_query = count_query.where(ThreatActor.motivation == motivation)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = (
        query.order_by(ThreatActor.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_threat_actor(
    db: AsyncSession, actor_id: uuid.UUID, data: ThreatActorUpdate
) -> ThreatActor | None:
    actor = await get_threat_actor(db, actor_id)
    if not actor:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(actor, field, value)

    actor.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(actor, ["observables", "techniques"])
    return actor


async def delete_threat_actor(
    db: AsyncSession, actor_id: uuid.UUID
) -> bool:
    actor = await get_threat_actor(db, actor_id)
    if not actor:
        return False
    await db.delete(actor)
    await db.flush()
    return True


async def link_observable(
    db: AsyncSession, actor_id: uuid.UUID, observable_id: uuid.UUID
) -> bool:
    # Verify both exist
    actor = await get_threat_actor(db, actor_id)
    if not actor:
        return False
    obs_result = await db.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    if not obs_result.scalar_one_or_none():
        return False

    await db.execute(
        insert(threat_actor_observables)
        .values(threat_actor_id=actor_id, observable_id=observable_id)
        .on_conflict_do_nothing()
    )
    await db.flush()
    return True


async def unlink_observable(
    db: AsyncSession, actor_id: uuid.UUID, observable_id: uuid.UUID
) -> bool:
    result = await db.execute(
        threat_actor_observables.delete().where(
            threat_actor_observables.c.threat_actor_id == actor_id,
            threat_actor_observables.c.observable_id == observable_id,
        )
    )
    await db.flush()
    return result.rowcount > 0


async def get_observables_for_actor(
    db: AsyncSession, actor_id: uuid.UUID
) -> list[Observable]:
    result = await db.execute(
        select(Observable)
        .join(
            threat_actor_observables,
            Observable.id == threat_actor_observables.c.observable_id,
        )
        .where(threat_actor_observables.c.threat_actor_id == actor_id)
    )
    return list(result.scalars().all())


async def link_technique(
    db: AsyncSession, actor_id: uuid.UUID, technique_id: uuid.UUID
) -> bool:
    actor = await get_threat_actor(db, actor_id)
    if not actor:
        return False
    tech_result = await db.execute(
        select(AttackTechnique).where(AttackTechnique.id == technique_id)
    )
    if not tech_result.scalar_one_or_none():
        return False

    await db.execute(
        insert(threat_actor_techniques)
        .values(threat_actor_id=actor_id, technique_id=technique_id)
        .on_conflict_do_nothing()
    )
    await db.flush()
    return True


async def unlink_technique(
    db: AsyncSession, actor_id: uuid.UUID, technique_id: uuid.UUID
) -> bool:
    result = await db.execute(
        threat_actor_techniques.delete().where(
            threat_actor_techniques.c.threat_actor_id == actor_id,
            threat_actor_techniques.c.technique_id == technique_id,
        )
    )
    await db.flush()
    return result.rowcount > 0


async def get_actors_for_observable(
    db: AsyncSession, observable_id: uuid.UUID
) -> list[ThreatActor]:
    """Get all threat actors linked to a specific observable."""
    result = await db.execute(
        select(ThreatActor)
        .join(
            threat_actor_observables,
            ThreatActor.id == threat_actor_observables.c.threat_actor_id,
        )
        .where(threat_actor_observables.c.observable_id == observable_id)
    )
    return list(result.scalars().all())
