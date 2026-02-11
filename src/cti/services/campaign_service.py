import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.campaign import Campaign, campaign_observables
from cti.models.observable import Observable
from cti.schemas.campaign import (
    CampaignCreate,
    CampaignTimelineResponse,
    CampaignUpdate,
    TimelineEvent,
)


async def create_campaign(
    db: AsyncSession,
    data: CampaignCreate,
    created_by: uuid.UUID | None = None,
) -> Campaign:
    campaign = Campaign(
        name=data.name,
        description=data.description,
        threat_actor_id=data.threat_actor_id,
        status=data.status,
        first_seen=data.first_seen,
        last_seen=data.last_seen,
        tlp=data.tlp,
        objective=data.objective,
        external_references=data.external_references,
        created_by=created_by,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign, ["threat_actor", "observables"])
    return campaign


async def get_campaign(
    db: AsyncSession, campaign_id: uuid.UUID
) -> Campaign | None:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    return result.scalar_one_or_none()


async def list_campaigns(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    name_search: str | None = None,
    status: str | None = None,
    threat_actor_id: uuid.UUID | None = None,
) -> tuple[list[Campaign], int]:
    query = select(Campaign)
    count_query = select(func.count(Campaign.id))

    if name_search:
        query = query.where(Campaign.name.ilike(f"%{name_search}%"))
        count_query = count_query.where(Campaign.name.ilike(f"%{name_search}%"))

    if status:
        query = query.where(Campaign.status == status)
        count_query = count_query.where(Campaign.status == status)

    if threat_actor_id:
        query = query.where(Campaign.threat_actor_id == threat_actor_id)
        count_query = count_query.where(Campaign.threat_actor_id == threat_actor_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = (
        query.order_by(Campaign.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_campaign(
    db: AsyncSession, campaign_id: uuid.UUID, data: CampaignUpdate
) -> Campaign | None:
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(campaign, ["threat_actor", "observables"])
    return campaign


async def delete_campaign(
    db: AsyncSession, campaign_id: uuid.UUID
) -> bool:
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return False
    await db.delete(campaign)
    await db.flush()
    return True


async def link_observable(
    db: AsyncSession, campaign_id: uuid.UUID, observable_id: uuid.UUID
) -> bool:
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return False
    obs_result = await db.execute(
        select(Observable).where(Observable.id == observable_id)
    )
    if not obs_result.scalar_one_or_none():
        return False

    await db.execute(
        insert(campaign_observables)
        .values(campaign_id=campaign_id, observable_id=observable_id)
        .on_conflict_do_nothing()
    )
    await db.flush()
    return True


async def unlink_observable(
    db: AsyncSession, campaign_id: uuid.UUID, observable_id: uuid.UUID
) -> bool:
    result = await db.execute(
        campaign_observables.delete().where(
            campaign_observables.c.campaign_id == campaign_id,
            campaign_observables.c.observable_id == observable_id,
        )
    )
    await db.flush()
    return result.rowcount > 0


async def get_observables_for_campaign(
    db: AsyncSession, campaign_id: uuid.UUID
) -> list[Observable]:
    result = await db.execute(
        select(Observable)
        .join(
            campaign_observables,
            Observable.id == campaign_observables.c.observable_id,
        )
        .where(campaign_observables.c.campaign_id == campaign_id)
    )
    return list(result.scalars().all())


async def get_campaign_timeline(
    db: AsyncSession, campaign_id: uuid.UUID
) -> CampaignTimelineResponse | None:
    """Build a chronological timeline of events for a campaign."""
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return None

    events: list[TimelineEvent] = []

    # Campaign creation event
    events.append(
        TimelineEvent(
            timestamp=campaign.created_at,
            event_type="campaign_created",
            description=f"Campaign '{campaign.name}' was created",
        )
    )

    # Campaign first_seen
    if campaign.first_seen:
        events.append(
            TimelineEvent(
                timestamp=campaign.first_seen,
                event_type="campaign_first_seen",
                description="Campaign first observed activity",
            )
        )

    # Campaign last_seen
    if campaign.last_seen and campaign.last_seen != campaign.first_seen:
        events.append(
            TimelineEvent(
                timestamp=campaign.last_seen,
                event_type="campaign_last_seen",
                description="Campaign most recent activity",
            )
        )

    # Observable events - when they were linked and their first/last seen dates
    obs_result = await db.execute(
        select(
            Observable,
            campaign_observables.c.created_at.label("linked_at"),
        )
        .join(
            campaign_observables,
            Observable.id == campaign_observables.c.observable_id,
        )
        .where(campaign_observables.c.campaign_id == campaign_id)
    )
    for row in obs_result.all():
        obs = row[0]
        linked_at = row[1]
        obs_type = obs.type.value if hasattr(obs.type, "value") else str(obs.type)

        if linked_at:
            events.append(
                TimelineEvent(
                    timestamp=linked_at,
                    event_type="observable_linked",
                    description=f"Observable {obs_type}:{obs.value} linked to campaign",
                    observable_id=obs.id,
                    observable_value=obs.value,
                    observable_type=obs_type,
                )
            )

        if obs.first_seen:
            events.append(
                TimelineEvent(
                    timestamp=obs.first_seen,
                    event_type="observable_first_seen",
                    description=f"Observable {obs_type}:{obs.value} first seen",
                    observable_id=obs.id,
                    observable_value=obs.value,
                    observable_type=obs_type,
                )
            )

    # Sort events by timestamp
    events.sort(key=lambda e: e.timestamp)

    return CampaignTimelineResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        events=events,
    )


async def get_campaigns_for_observable(
    db: AsyncSession, observable_id: uuid.UUID
) -> list[Campaign]:
    """Get all campaigns linked to a specific observable."""
    result = await db.execute(
        select(Campaign)
        .join(
            campaign_observables,
            Campaign.id == campaign_observables.c.campaign_id,
        )
        .where(campaign_observables.c.observable_id == observable_id)
    )
    return list(result.scalars().all())


async def get_campaigns_for_threat_actor(
    db: AsyncSession, actor_id: uuid.UUID
) -> list[Campaign]:
    """Get all campaigns associated with a specific threat actor."""
    result = await db.execute(
        select(Campaign).where(Campaign.threat_actor_id == actor_id)
    )
    return list(result.scalars().all())
