"""Test observable endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_observables_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/observables")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_observables_with_filters(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/observables",
        params={"type": "ip-addr", "confidence_min": 50, "page": 1, "size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_observable_not_found(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/observables/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_observable_source_exposes_native_confidence(client, db_session):
    from cti.feeds.base import RawObservable
    from cti.models.feed import Feed, FeedType
    from cti.services import observable_service

    feed = Feed(name="NF", feed_type=FeedType.FILE, default_confidence=80)
    db_session.add(feed)
    await db_session.commit()
    await observable_service.bulk_upsert_from_feed(
        db_session, feed, [RawObservable(type="ip-addr", value="5.5.5.5", native_confidence=80)]
    )

    resp = await client.get("/api/v1/observables", params={"q": "5.5.5.5"})
    assert resp.status_code == 200
    src = resp.json()["items"][0]["sources"][0]
    assert src["native_confidence"] == 80
