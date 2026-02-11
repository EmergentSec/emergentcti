import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AdminUser, AnalystUser, CurrentUser
from cti.schemas.bulk import BulkFeedUpdate, BulkIds
from cti.schemas.feed import FeedCreate, FeedResponse, FeedRunResponse, FeedUpdate
from cti.services import feed_service

router = APIRouter()


@router.get("", response_model=list[FeedResponse])
async def list_feeds(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[FeedResponse]:
    feeds = await feed_service.list_feeds(db)
    return [FeedResponse.model_validate(f) for f in feeds]


@router.post("", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(
    data: FeedCreate,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> FeedResponse:
    feed = await feed_service.create_feed(db, data)
    return FeedResponse.model_validate(feed)


@router.patch("/bulk", status_code=status.HTTP_200_OK)
async def bulk_update_feeds(
    data: BulkFeedUpdate,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await feed_service.bulk_update_feeds(db, data.ids, enabled=data.enabled)
    return {"updated": count}


@router.delete("/bulk", status_code=status.HTTP_200_OK)
async def bulk_delete_feeds(
    data: BulkIds,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await feed_service.bulk_delete_feeds(db, data.ids)
    return {"deleted": count}


@router.post("/bulk/trigger", status_code=status.HTTP_202_ACCEPTED)
async def bulk_trigger_feeds(
    data: BulkIds,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from cti.worker import run_feed_task

    triggered = 0
    for feed_id in data.ids:
        feed = await feed_service.get_feed(db, feed_id)
        if feed:
            run_feed_task.delay(str(feed_id))
            triggered += 1
    return {"triggered": triggered}


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(
    feed_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> FeedResponse:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return FeedResponse.model_validate(feed)


@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: uuid.UUID,
    data: FeedUpdate,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> FeedResponse:
    feed = await feed_service.update_feed(db, feed_id, data)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    return FeedResponse.model_validate(feed)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(
    feed_id: uuid.UUID,
    _user: AdminUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await feed_service.delete_feed(db, feed_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")


@router.post("/{feed_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_feed(
    feed_id: uuid.UUID,
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")

    from cti.worker import run_feed_task

    run_feed_task.delay(str(feed_id))
    return {"status": "triggered", "feed_id": str(feed_id)}


@router.get("/{feed_id}/runs", response_model=list[FeedRunResponse])
async def get_feed_runs(
    feed_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[FeedRunResponse]:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    runs = await feed_service.get_feed_runs(db, feed_id)
    return [FeedRunResponse.model_validate(r) for r in runs]
