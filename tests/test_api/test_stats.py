# tests/test_api/test_stats.py
import pytest

from cti.models.observable import Observable, ObservableType


@pytest.mark.asyncio
async def test_stats_includes_14d_ingestion_series(client, db_session):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    series = resp.json()["daily_ingest_14d"]
    assert isinstance(series, list)
    assert len(series) == 14
    assert all(set(p) == {"date", "count"} for p in series)
    # oldest first, newest last
    assert series[0]["date"] < series[-1]["date"]
    assert all(isinstance(p["count"], int) for p in series)


@pytest.mark.asyncio
async def test_stats_includes_distribution_and_errors(client, db_session):
    db_session.add_all([
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.1", confidence_score=95),  # critical
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.2", confidence_score=65),  # high
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.3", confidence_score=45),  # medium
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.4", confidence_score=10),  # low
    ])
    await db_session.commit()

    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_distribution"] == {"critical": 1, "high": 1, "medium": 1, "low": 1}
    assert data["feed_errors_24h"] == 0
