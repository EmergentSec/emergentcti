import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.core.elasticsearch import get_es_client
from cti.models.observable import Observable, ObservableType
from cti.schemas.bulk import BulkIds, BulkObservableUpdate
from cti.schemas.note import NoteCreate, NoteResponse
from cti.schemas.observable import (
    ObservableCreate,
    ObservableListResponse,
    ObservableResponse,
    ObservableStatsResponse,
    ObservableUpdate,
)
from cti.services import note_service, observable_service, search_service

logger = logging.getLogger(__name__)


def _observable_to_es_doc(obs: ObservableResponse) -> dict:
    """Convert an ObservableResponse to an Elasticsearch document."""
    return {
        "id": str(obs.id),
        "type": obs.type.value if hasattr(obs.type, "value") else str(obs.type),
        "value": obs.value,
        "confidence_score": obs.confidence_score,
        "first_seen": obs.first_seen.isoformat() if obs.first_seen else None,
        "last_seen": obs.last_seen.isoformat() if obs.last_seen else None,
        "tlp": obs.tlp,
        "tags": obs.tags,
        "category": obs.category,
        "created_at": obs.created_at.isoformat() if obs.created_at else None,
        "updated_at": obs.updated_at.isoformat() if obs.updated_at else None,
    }

router = APIRouter()


@router.get("", response_model=ObservableListResponse)
async def list_observables(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    type: ObservableType | None = None,
    value: str | None = None,
    confidence_min: int | None = Query(default=None, ge=0, le=100),
    tlp: str | None = None,
    feed_id: uuid.UUID | None = None,
) -> ObservableListResponse:
    items, total = await observable_service.list_observables(
        db,
        page=page,
        size=size,
        type_filter=type,
        value_search=value,
        confidence_min=confidence_min,
        tlp=tlp,
        feed_id=feed_id,
    )
    return ObservableListResponse(
        items=[ObservableResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=ObservableResponse, status_code=status.HTTP_201_CREATED)
async def create_observable(
    data: ObservableCreate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> ObservableResponse:
    observable = await observable_service.create_observable(db, data)
    response = ObservableResponse.model_validate(observable)
    try:
        es = get_es_client()
        await search_service.index_observable(es, _observable_to_es_doc(response))
        await es.close()
    except Exception:
        logger.warning("Failed to index observable in Elasticsearch", exc_info=True)
    return response


@router.get("/stats", response_model=ObservableStatsResponse)
async def observable_stats(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ObservableStatsResponse:
    stats = await observable_service.get_observable_stats(db)
    return ObservableStatsResponse(**stats)


@router.put("/bulk", status_code=status.HTTP_200_OK)
async def bulk_update_observables(
    data: BulkObservableUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await observable_service.bulk_update_observables(
        db,
        ids=data.ids,
        tlp=data.tlp,
        confidence_score=data.confidence_score,
        tags=data.tags,
        add_tags=data.add_tags,
        category=data.category,
    )
    try:
        es = get_es_client()
        result = await db.execute(select(Observable).where(Observable.id.in_(data.ids)))
        docs = [
            _observable_to_es_doc(ObservableResponse.model_validate(obs))
            for obs in result.scalars()
        ]
        await search_service.bulk_index_observables(es, docs)
        await es.close()
    except Exception:
        logger.warning("Failed to bulk index updated observables to ES", exc_info=True)
    return {"updated": count}


@router.delete("/bulk", status_code=status.HTTP_200_OK)
async def bulk_delete_observables(
    data: BulkIds,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await observable_service.bulk_delete_observables(db, data.ids)
    try:
        es = get_es_client()
        for obs_id in data.ids:
            await es.delete(index="cti-observables", id=str(obs_id), ignore=[404])
        await es.close()
    except Exception:
        logger.warning("Failed to delete observables from ES", exc_info=True)
    return {"deleted": count}


@router.post("/bulk/enrich")
async def bulk_enrich(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: AnalystUser = ...,
) -> dict:
    """Dispatch enrichment tasks for multiple observables."""
    from cti.enrichment.registry import get_enrichment_provider
    from cti.models.enrichment import EnrichmentConfig
    from cti.worker import enrich_observable_task

    ids = [uuid.UUID(i) for i in body.get("ids", [])]

    # Get all enabled configs with API keys
    configs_result = await db.execute(
        select(EnrichmentConfig).where(
            EnrichmentConfig.enabled.is_(True),
            EnrichmentConfig.api_key_encrypted.isnot(None),
        )
    )
    enabled_providers = [c.provider_name for c in configs_result.scalars()]

    dispatched = 0
    for obs_id in ids:
        result = await db.execute(select(Observable).where(Observable.id == obs_id))
        observable = result.scalar_one_or_none()
        if not observable:
            continue
        for provider_name in enabled_providers:
            provider = get_enrichment_provider(provider_name)
            if provider and provider.supports_type(observable.type.value):
                enrich_observable_task.delay(str(obs_id), provider_name, str(user.id))
                dispatched += 1

    return {"dispatched": dispatched}


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ObservableResponse:
    observable = await observable_service.get_observable(db, observable_id)
    if not observable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observable not found")
    return ObservableResponse.model_validate(observable)


@router.put("/{observable_id}", response_model=ObservableResponse)
async def update_observable(
    observable_id: uuid.UUID,
    data: ObservableUpdate,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> ObservableResponse:
    observable = await observable_service.update_observable(db, observable_id, data)
    if not observable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observable not found")
    response = ObservableResponse.model_validate(observable)
    try:
        es = get_es_client()
        await search_service.index_observable(es, _observable_to_es_doc(response))
        await es.close()
    except Exception:
        logger.warning("Failed to index observable in Elasticsearch", exc_info=True)
    return response


@router.delete("/{observable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observable(
    observable_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await observable_service.delete_observable(db, observable_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observable not found")
    try:
        es = get_es_client()
        await es.delete(index="cti-observables", id=str(observable_id), ignore=[404])
        await es.close()
    except Exception:
        logger.warning("Failed to delete observable from Elasticsearch", exc_info=True)


@router.get("/{observable_id}/notes", response_model=list[NoteResponse])
async def list_observable_notes(
    observable_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    observable = await observable_service.get_observable(db, observable_id)
    if not observable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observable not found")
    notes = await note_service.list_notes(db, observable_id)
    return [NoteResponse.from_orm_note(n) for n in notes]


@router.post(
    "/{observable_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_observable_note(
    observable_id: uuid.UUID,
    data: NoteCreate,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    observable = await observable_service.get_observable(db, observable_id)
    if not observable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observable not found")
    note = await note_service.create_note(db, observable_id, user.id, data.content)
    return NoteResponse.from_orm_note(note)


@router.delete(
    "/{observable_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_observable_note(
    observable_id: uuid.UUID,
    note_id: uuid.UUID,
    user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await note_service.delete_note(db, note_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or unauthorized"
        )
