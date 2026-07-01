import pytest
from sqlalchemy import select

from cti.feeds.base import RawObservable
from cti.models.feed import Feed, FeedType
from cti.models.observable_source import ObservableSource
from cti.services import observable_service


@pytest.mark.asyncio
async def test_ingest_sets_native_confidence(db_session):
    feed = Feed(name="T", feed_type=FeedType.FILE, default_confidence=70)
    db_session.add(feed)
    await db_session.commit()

    raws = [RawObservable(type="ip-addr", value="1.2.3.4", native_confidence=90)]
    await observable_service.bulk_upsert_from_feed(db_session, feed, raws)

    src = (await db_session.execute(select(ObservableSource))).scalar_one()
    assert src.source_confidence == 90
    assert src.native_confidence == 90


@pytest.mark.asyncio
async def test_ingest_conflict_retains_greatest_native_confidence(db_session):
    feed = Feed(name="T", feed_type=FeedType.FILE, default_confidence=70)
    db_session.add(feed)
    await db_session.commit()

    # Ingest same observable with native_confidence=90
    raws = [RawObservable(type="ip-addr", value="1.2.3.4", native_confidence=90)]
    await observable_service.bulk_upsert_from_feed(db_session, feed, raws)
    await db_session.commit()

    # Ingest same observable again with lower native_confidence=60
    raws = [RawObservable(type="ip-addr", value="1.2.3.4", native_confidence=60)]
    await observable_service.bulk_upsert_from_feed(db_session, feed, raws)

    # Should have exactly one source row with native_confidence=90 (greatest retained)
    sources = (await db_session.execute(select(ObservableSource))).scalars().all()
    assert len(sources) == 1
    assert sources[0].native_confidence == 90
