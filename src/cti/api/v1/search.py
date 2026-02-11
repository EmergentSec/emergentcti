from fastapi import APIRouter, Depends, Query

from cti.core.dependencies import CurrentUser
from cti.core.elasticsearch import get_es_client
from cti.models.observable import ObservableType
from cti.schemas.search import SearchResponse
from cti.services import search_service

router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search(
    _user: CurrentUser,
    q: str = Query(min_length=1),
    type: ObservableType | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    confidence_max: int | None = Query(default=None, ge=0, le=100),
    tags: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> SearchResponse:
    es = get_es_client()
    try:
        tag_list = tags.split(",") if tags else None
        return await search_service.search_observables(
            es,
            q=q,
            type_filter=type.value if type else None,
            date_from=date_from,
            date_to=date_to,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            tags=tag_list,
            page=page,
            size=size,
        )
    finally:
        await es.close()
