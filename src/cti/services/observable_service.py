import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import Observable, ObservableType, observable_tags
from cti.models.tag import Tag
from cti.schemas.observable import ObservableCreate, ObservableUpdate


async def _resolve_tags(db: AsyncSession, tag_names: list[str]) -> list[Tag]:
    """Resolve tag names to Tag objects, creating new tags as needed."""
    if not tag_names:
        return []
    tags: list[Tag] = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        result = await db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


async def create_observable(db: AsyncSession, data: ObservableCreate) -> Observable:
    now = datetime.now(UTC)
    stmt = (
        insert(Observable)
        .values(
            type=data.type,
            value=data.value,
            confidence_score=data.confidence_score,
            first_seen=data.first_seen or now,
            last_seen=data.last_seen or now,
            tlp=data.tlp,
            context=data.context,
            category=data.category,
        )
        .on_conflict_do_update(
            constraint="uq_observable_type_value",
            set_={
                "last_seen": func.greatest(Observable.last_seen, data.last_seen or now),
                "confidence_score": func.greatest(Observable.confidence_score, data.confidence_score),
                "updated_at": now,
            },
        )
        .returning(Observable)
    )
    result = await db.execute(stmt)
    observable = result.scalar_one()

    if data.tags:
        resolved_tags = await _resolve_tags(db, data.tags)
        for tag in resolved_tags:
            await db.execute(
                insert(observable_tags)
                .values(observable_id=observable.id, tag_id=tag.id)
                .on_conflict_do_nothing()
            )

    await db.flush()
    # Refresh to load relationships
    await db.refresh(observable, ["tags", "sources"])
    return observable


async def get_observable(db: AsyncSession, observable_id: uuid.UUID) -> Observable | None:
    result = await db.execute(select(Observable).where(Observable.id == observable_id))
    return result.scalar_one_or_none()


async def list_observables(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    type_filter: ObservableType | None = None,
    value_search: str | None = None,
    confidence_min: int | None = None,
    tlp: str | None = None,
    feed_id: uuid.UUID | None = None,
) -> tuple[list[Observable], int]:
    from cti.models.observable import observable_sources

    query = select(Observable)
    count_query = select(func.count(Observable.id))

    if feed_id:
        query = query.join(observable_sources).where(observable_sources.c.feed_id == feed_id)
        count_query = count_query.join(
            observable_sources,
        ).where(observable_sources.c.feed_id == feed_id)

    if type_filter:
        query = query.where(Observable.type == type_filter)
        count_query = count_query.where(Observable.type == type_filter)

    if value_search:
        query = query.where(Observable.value.ilike(f"%{value_search}%"))
        count_query = count_query.where(Observable.value.ilike(f"%{value_search}%"))

    if confidence_min is not None:
        query = query.where(Observable.confidence_score >= confidence_min)
        count_query = count_query.where(Observable.confidence_score >= confidence_min)

    if tlp:
        query = query.where(Observable.tlp == tlp)
        count_query = count_query.where(Observable.tlp == tlp)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Observable.updated_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_observable(
    db: AsyncSession, observable_id: uuid.UUID, data: ObservableUpdate
) -> Observable | None:
    observable = await get_observable(db, observable_id)
    if not observable:
        return None

    update_data = data.model_dump(exclude_unset=True)
    tag_names = update_data.pop("tags", None)

    for field, value in update_data.items():
        setattr(observable, field, value)

    observable.updated_at = datetime.now(UTC)

    if tag_names is not None:
        resolved_tags = await _resolve_tags(db, tag_names)
        await db.execute(
            observable_tags.delete().where(observable_tags.c.observable_id == observable_id)
        )
        for tag in resolved_tags:
            await db.execute(
                insert(observable_tags)
                .values(observable_id=observable_id, tag_id=tag.id)
                .on_conflict_do_nothing()
            )

    await db.flush()
    await db.refresh(observable, ["tags", "sources"])
    return observable


async def delete_observable(db: AsyncSession, observable_id: uuid.UUID) -> bool:
    observable = await get_observable(db, observable_id)
    if not observable:
        return False
    await db.delete(observable)
    await db.flush()
    return True


async def bulk_create_observables(
    db: AsyncSession,
    items: list[ObservableCreate],
    feed_id: uuid.UUID | None = None,
) -> int:
    from cti.models.observable import observable_sources

    count = 0
    for item in items:
        now = datetime.now(UTC)
        stmt = (
            insert(Observable)
            .values(
                type=item.type,
                value=item.value,
                confidence_score=item.confidence_score,
                first_seen=item.first_seen or now,
                last_seen=item.last_seen or now,
                tlp=item.tlp,
                context=item.context,
            )
            .on_conflict_do_update(
                constraint="uq_observable_type_value",
                set_={
                    "last_seen": func.greatest(Observable.last_seen, item.last_seen or now),
                    "confidence_score": func.greatest(Observable.confidence_score, item.confidence_score),
                    "updated_at": now,
                },
            )
            .returning(Observable.id)
        )
        result = await db.execute(stmt)
        obs_id = result.scalar_one()

        if feed_id:
            await db.execute(
                insert(observable_sources)
                .values(observable_id=obs_id, feed_id=feed_id)
                .on_conflict_do_nothing()
            )

        count += 1

    await db.flush()
    return count


async def get_observable_stats(db: AsyncSession) -> dict:
    total_result = await db.execute(select(func.count(Observable.id)))
    total = total_result.scalar_one()

    type_result = await db.execute(
        select(Observable.type, func.count(Observable.id)).group_by(Observable.type)
    )
    by_type = {row[0].value: row[1] for row in type_result.all()}

    return {"total": total, "by_type": by_type}


async def bulk_update_observables(
    db: AsyncSession,
    ids: list[uuid.UUID],
    tlp: str | None = None,
    confidence_score: int | None = None,
    tags: list[str] | None = None,
    add_tags: list[str] | None = None,
    category: str | None = None,
) -> int:
    """Bulk update observables by IDs."""
    from sqlalchemy import update as sa_update
    from sqlalchemy.dialects.postgresql import insert

    values: dict = {}
    if tlp is not None:
        values["tlp"] = tlp
    if confidence_score is not None:
        values["confidence_score"] = confidence_score
    if category is not None:
        values["category"] = category

    if values:
        values["updated_at"] = datetime.now(UTC)
        await db.execute(
            sa_update(Observable).where(Observable.id.in_(ids)).values(**values)
        )

    # Handle tag replacement
    if tags is not None:
        resolved = await _resolve_tags(db, tags)
        # Clear existing tags for all selected observables
        await db.execute(
            observable_tags.delete().where(observable_tags.c.observable_id.in_(ids))
        )
        # Add new tags
        for obs_id in ids:
            for tag in resolved:
                await db.execute(
                    insert(observable_tags)
                    .values(observable_id=obs_id, tag_id=tag.id)
                    .on_conflict_do_nothing()
                )

    # Handle tag append
    if add_tags is not None:
        resolved = await _resolve_tags(db, add_tags)
        for obs_id in ids:
            for tag in resolved:
                await db.execute(
                    insert(observable_tags)
                    .values(observable_id=obs_id, tag_id=tag.id)
                    .on_conflict_do_nothing()
                )

    await db.flush()
    return len(ids)


async def bulk_delete_observables(db: AsyncSession, ids: list[uuid.UUID]) -> int:
    """Bulk delete observables by IDs."""
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        sa_delete(Observable).where(Observable.id.in_(ids))
    )
    await db.flush()
    return result.rowcount
