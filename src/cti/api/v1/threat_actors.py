import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.threat_actor import (
    ObservableLink,
    TechniqueLink,
    ThreatActorCreate,
    ThreatActorListResponse,
    ThreatActorResponse,
    ThreatActorUpdate,
)
from cti.services import campaign_service, threat_actor_service

router = APIRouter()


@router.get("", response_model=ThreatActorListResponse)
async def list_threat_actors(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    name: str | None = None,
    country: str | None = None,
    motivation: str | None = None,
) -> ThreatActorListResponse:
    items, total = await threat_actor_service.list_threat_actors(
        db,
        page=page,
        size=size,
        name_search=name,
        country=country,
        motivation=motivation,
    )
    return ThreatActorListResponse(
        items=[ThreatActorResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=ThreatActorResponse, status_code=status.HTTP_201_CREATED)
async def create_threat_actor(
    data: ThreatActorCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> ThreatActorResponse:
    actor = await threat_actor_service.create_threat_actor(db, data, created_by=user.id)
    return ThreatActorResponse.model_validate(actor)


@router.get("/{actor_id}", response_model=ThreatActorResponse)
async def get_threat_actor(
    actor_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ThreatActorResponse:
    actor = await threat_actor_service.get_threat_actor(db, actor_id)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor not found",
        )
    return ThreatActorResponse.model_validate(actor)


@router.put("/{actor_id}", response_model=ThreatActorResponse)
async def update_threat_actor(
    actor_id: uuid.UUID,
    data: ThreatActorUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> ThreatActorResponse:
    actor = await threat_actor_service.update_threat_actor(db, actor_id, data)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor not found",
        )
    return ThreatActorResponse.model_validate(actor)


@router.delete("/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threat_actor(
    actor_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await threat_actor_service.delete_threat_actor(db, actor_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor not found",
        )


@router.get("/{actor_id}/observables")
async def get_actor_observables(
    actor_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    actor = await threat_actor_service.get_threat_actor(db, actor_id)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor not found",
        )
    observables = await threat_actor_service.get_observables_for_actor(db, actor_id)
    return [
        {
            "id": str(o.id),
            "type": o.type.value if hasattr(o.type, "value") else str(o.type),
            "value": o.value,
        }
        for o in observables
    ]


@router.post("/{actor_id}/observables", status_code=status.HTTP_201_CREATED)
async def link_actor_observable(
    actor_id: uuid.UUID,
    data: ObservableLink,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success = await threat_actor_service.link_observable(
        db, actor_id, data.observable_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor or observable not found",
        )
    return {"status": "linked"}


@router.delete("/{actor_id}/observables/{observable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_actor_observable(
    actor_id: uuid.UUID,
    observable_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    success = await threat_actor_service.unlink_observable(db, actor_id, observable_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )


@router.post("/{actor_id}/techniques", status_code=status.HTTP_201_CREATED)
async def link_actor_technique(
    actor_id: uuid.UUID,
    data: TechniqueLink,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success = await threat_actor_service.link_technique(
        db, actor_id, data.technique_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor or technique not found",
        )
    return {"status": "linked"}


@router.delete("/{actor_id}/techniques/{technique_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_actor_technique(
    actor_id: uuid.UUID,
    technique_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    success = await threat_actor_service.unlink_technique(db, actor_id, technique_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )


@router.get("/{actor_id}/campaigns")
async def get_actor_campaigns(
    actor_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    actor = await threat_actor_service.get_threat_actor(db, actor_id)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Threat actor not found",
        )
    campaigns = await campaign_service.get_campaigns_for_threat_actor(db, actor_id)
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "status": c.status,
            "first_seen": c.first_seen.isoformat() if c.first_seen else None,
            "last_seen": c.last_seen.isoformat() if c.last_seen else None,
        }
        for c in campaigns
    ]
