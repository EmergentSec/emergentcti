import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignObservableLink,
    CampaignResponse,
    CampaignTimelineResponse,
    CampaignUpdate,
)
from cti.services import campaign_service

router = APIRouter()


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    name: str | None = None,
    campaign_status: str | None = Query(default=None, alias="status"),
    threat_actor_id: uuid.UUID | None = None,
) -> CampaignListResponse:
    items, total = await campaign_service.list_campaigns(
        db,
        page=page,
        size=size,
        name_search=name,
        status=campaign_status,
        threat_actor_id=threat_actor_id,
    )
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.create_campaign(db, data, created_by=user.id)
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return CampaignResponse.model_validate(campaign)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await campaign_service.update_campaign(db, campaign_id, data)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return CampaignResponse.model_validate(campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await campaign_service.delete_campaign(db, campaign_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )


@router.get("/{campaign_id}/observables")
async def get_campaign_observables(
    campaign_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    campaign = await campaign_service.get_campaign(db, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    observables = await campaign_service.get_observables_for_campaign(db, campaign_id)
    return [
        {
            "id": str(o.id),
            "type": o.type.value if hasattr(o.type, "value") else str(o.type),
            "value": o.value,
        }
        for o in observables
    ]


@router.post("/{campaign_id}/observables", status_code=status.HTTP_201_CREATED)
async def link_campaign_observable(
    campaign_id: uuid.UUID,
    data: CampaignObservableLink,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success = await campaign_service.link_observable(
        db, campaign_id, data.observable_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign or observable not found",
        )
    return {"status": "linked"}


@router.delete(
    "/{campaign_id}/observables/{observable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_campaign_observable(
    campaign_id: uuid.UUID,
    observable_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    success = await campaign_service.unlink_observable(db, campaign_id, observable_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found",
        )


@router.get("/{campaign_id}/timeline", response_model=CampaignTimelineResponse)
async def get_campaign_timeline(
    campaign_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CampaignTimelineResponse:
    timeline = await campaign_service.get_campaign_timeline(db, campaign_id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return timeline
