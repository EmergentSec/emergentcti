# tests/test_api/test_stats.py
import pytest

from cti.models.observable import Observable, ObservableType


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
