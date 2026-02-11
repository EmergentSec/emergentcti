import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AnalystUser, CurrentUser
from cti.schemas.saved_search import (
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
)
from cti.services import saved_search_service

router = APIRouter()


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[SavedSearchResponse]:
    searches = await saved_search_service.list_saved_searches(db, user.id)
    return [SavedSearchResponse.model_validate(s) for s in searches]


@router.post(
    "",
    response_model=SavedSearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_search(
    data: SavedSearchCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> SavedSearchResponse:
    try:
        saved_search = await saved_search_service.create_saved_search(
            db, user.id, data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from None
    return SavedSearchResponse.model_validate(saved_search)


@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: uuid.UUID,
    data: SavedSearchUpdate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> SavedSearchResponse:
    saved_search = await saved_search_service.update_saved_search(
        db, search_id, user.id, data
    )
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found or unauthorized",
        )
    return SavedSearchResponse.model_validate(saved_search)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: uuid.UUID,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await saved_search_service.delete_saved_search(
        db, search_id, user.id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found or unauthorized",
        )


@router.post(
    "/{search_id}/default",
    response_model=SavedSearchResponse,
)
async def set_default_search(
    search_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SavedSearchResponse:
    saved_search = await saved_search_service.set_default_search(
        db, search_id, user.id
    )
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found or unauthorized",
        )
    return SavedSearchResponse.model_validate(saved_search)
