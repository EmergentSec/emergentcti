import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.feed import FeedType
from cti.schemas.feed import FeedCreate, FeedUpdate
from cti.services import feed_service


@pytest.mark.asyncio
async def test_create_feed(db: AsyncSession):
    data = FeedCreate(
        name="Test API Feed",
        description="Test feed",
        feed_type=FeedType.api,
        url="https://api.example.com/iocs",
        schedule_cron="0 */6 * * *",
    )
    feed = await feed_service.create_feed(db, data)
    assert feed.name == "Test API Feed"
    assert feed.feed_type == FeedType.api
    assert feed.enabled is True


@pytest.mark.asyncio
async def test_create_feed_with_auth(db: AsyncSession):
    data = FeedCreate(
        name="Auth Feed",
        feed_type=FeedType.api,
        url="https://secure.example.com",
        auth_config={"api_key": "secret123", "header": "X-API-Key"},
    )
    feed = await feed_service.create_feed(db, data)
    assert feed.auth_config_encrypted is not None

    # Decrypt and verify
    auth = feed_service.get_feed_auth_config(feed)
    assert auth is not None
    assert auth["api_key"] == "secret123"


@pytest.mark.asyncio
async def test_list_feeds(db: AsyncSession):
    await feed_service.create_feed(
        db, FeedCreate(name="List Feed 1", feed_type=FeedType.api)
    )
    await feed_service.create_feed(
        db, FeedCreate(name="List Feed 2", feed_type=FeedType.file)
    )

    feeds = await feed_service.list_feeds(db)
    assert len(feeds) >= 2


@pytest.mark.asyncio
async def test_update_feed(db: AsyncSession):
    feed = await feed_service.create_feed(
        db, FeedCreate(name="Update Feed", feed_type=FeedType.api)
    )

    updated = await feed_service.update_feed(
        db, feed.id, FeedUpdate(name="Updated Feed", enabled=False)
    )
    assert updated is not None
    assert updated.name == "Updated Feed"
    assert updated.enabled is False


@pytest.mark.asyncio
async def test_delete_feed(db: AsyncSession):
    feed = await feed_service.create_feed(
        db, FeedCreate(name="Delete Feed", feed_type=FeedType.scraper)
    )

    deleted = await feed_service.delete_feed(db, feed.id)
    assert deleted is True

    found = await feed_service.get_feed(db, feed.id)
    assert found is None
