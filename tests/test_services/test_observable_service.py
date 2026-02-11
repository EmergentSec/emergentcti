import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate
from cti.services import observable_service


@pytest.mark.asyncio
async def test_create_observable(db: AsyncSession):
    data = ObservableCreate(
        type=ObservableType.ip_addr,
        value="192.168.1.100",
        confidence_score=75,
    )
    obs = await observable_service.create_observable(db, data)
    assert obs.type == ObservableType.ip_addr
    assert obs.value == "192.168.1.100"
    assert obs.confidence_score == 75


@pytest.mark.asyncio
async def test_dedup_raises_confidence(db: AsyncSession):
    data1 = ObservableCreate(
        type=ObservableType.ip_addr,
        value="10.0.0.50",
        confidence_score=40,
    )
    await observable_service.create_observable(db, data1)

    data2 = ObservableCreate(
        type=ObservableType.ip_addr,
        value="10.0.0.50",
        confidence_score=90,
    )
    obs = await observable_service.create_observable(db, data2)
    assert obs.confidence_score == 90


@pytest.mark.asyncio
async def test_dedup_never_lowers_confidence(db: AsyncSession):
    data1 = ObservableCreate(
        type=ObservableType.ip_addr,
        value="10.0.0.51",
        confidence_score=90,
    )
    await observable_service.create_observable(db, data1)

    data2 = ObservableCreate(
        type=ObservableType.ip_addr,
        value="10.0.0.51",
        confidence_score=30,
    )
    obs = await observable_service.create_observable(db, data2)
    assert obs.confidence_score == 90


@pytest.mark.asyncio
async def test_list_observables_pagination(db: AsyncSession):
    for i in range(5):
        await observable_service.create_observable(
            db,
            ObservableCreate(type=ObservableType.ip_addr, value=f"10.1.{i}.1"),
        )

    items, total = await observable_service.list_observables(db, page=1, size=3)
    assert total == 5
    assert len(items) == 3


@pytest.mark.asyncio
async def test_list_observables_type_filter(db: AsyncSession):
    await observable_service.create_observable(
        db, ObservableCreate(type=ObservableType.ip_addr, value="10.2.0.1")
    )
    await observable_service.create_observable(
        db, ObservableCreate(type=ObservableType.domain_name, value="test.example.com")
    )

    items, total = await observable_service.list_observables(
        db, type_filter=ObservableType.domain_name
    )
    assert total == 1
    assert items[0].type == ObservableType.domain_name


@pytest.mark.asyncio
async def test_delete_observable(db: AsyncSession):
    obs = await observable_service.create_observable(
        db, ObservableCreate(type=ObservableType.ip_addr, value="10.3.0.1")
    )
    deleted = await observable_service.delete_observable(db, obs.id)
    assert deleted is True

    found = await observable_service.get_observable(db, obs.id)
    assert found is None


@pytest.mark.asyncio
async def test_get_observable_stats(db: AsyncSession):
    await observable_service.create_observable(
        db, ObservableCreate(type=ObservableType.ip_addr, value="10.4.0.1")
    )
    await observable_service.create_observable(
        db, ObservableCreate(type=ObservableType.domain_name, value="stats.example.com")
    )

    stats = await observable_service.get_observable_stats(db)
    assert stats["total"] >= 2
    assert "ip-addr" in stats["by_type"]
