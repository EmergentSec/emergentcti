import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.attack import (
    HeatmapResponse,
    ObservableTechniqueCreate,
    ObservableTechniqueResponse,
    TacticResponse,
    TechniqueResponse,
)
from cti.services import attack_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tactics", response_model=list[TacticResponse])
async def list_tactics(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[TacticResponse]:
    """List all MITRE ATT&CK tactics in display order."""
    tactics = await attack_service.list_tactics(db)
    return [TacticResponse.model_validate(t) for t in tactics]


@router.get(
    "/techniques", response_model=list[TechniqueResponse]
)
async def list_techniques(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    tactic_id: uuid.UUID | None = Query(default=None),
) -> list[TechniqueResponse]:
    """List ATT&CK techniques, optionally filtered by tactic."""
    techniques = await attack_service.list_techniques(
        db, tactic_id=tactic_id
    )
    return [
        TechniqueResponse.model_validate(t) for t in techniques
    ]


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_attack_data(
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Force re-sync of MITRE ATT&CK data from upstream."""
    await attack_service.sync_attack_data(db)
    return {"status": "synced"}


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """Get ATT&CK heatmap data (observable counts per technique/tactic)."""
    return await attack_service.get_heatmap_data(db)


@router.get(
    "/observables/{observable_id}/techniques",
    response_model=list[ObservableTechniqueResponse],
)
async def list_observable_techniques(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[ObservableTechniqueResponse]:
    """List ATT&CK techniques mapped to an observable."""
    mappings = await attack_service.get_observable_techniques(
        db, observable_id
    )
    return [
        ObservableTechniqueResponse.model_validate(m)
        for m in mappings
    ]


@router.post(
    "/observables/{observable_id}/techniques",
    response_model=ObservableTechniqueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def map_observable_technique(
    observable_id: uuid.UUID,
    data: ObservableTechniqueCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> ObservableTechniqueResponse:
    """Map an ATT&CK technique to an observable."""
    try:
        mapping = await attack_service.map_observable_to_technique(
            db,
            observable_id=observable_id,
            technique_id=data.technique_id,
            user_id=user.id,
        )
    except Exception as exc:
        error_msg = str(exc).lower()
        if "unique" in error_msg or "duplicate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Technique already mapped to this observable",
            ) from exc
        if "foreign" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Observable or technique not found",
            ) from exc
        raise
    return ObservableTechniqueResponse.model_validate(mapping)


@router.delete(
    "/observables/{observable_id}/techniques/{technique_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unmap_observable_technique(
    observable_id: uuid.UUID,
    technique_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an ATT&CK technique mapping from an observable."""
    deleted = await attack_service.unmap_observable_from_technique(
        db,
        observable_id=observable_id,
        technique_id=technique_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technique mapping not found",
        )
