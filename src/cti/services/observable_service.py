"""Observable CRUD, bulk upsert, and blocklist query service."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cti.feeds.base import RawObservable
from cti.models.feed import Feed
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services.confidence import compute_source_confidence

logger = logging.getLogger(__name__)

# Maximum rows per INSERT batch to avoid excessive memory usage.
_BATCH_SIZE = 500

# Deadlock retry parameters.
_MAX_RETRIES = 3
_BASE_DELAY = 0.5  # seconds


async def get_observables(
    db: AsyncSession,
    q: str | None = None,
    obs_type: ObservableType | None = None,
    confidence_min: int | None = None,
    feed_id: uuid.UUID | None = None,
    manual_only: bool = False,
    last_seen_after: datetime | None = None,
    page: int = 1,
    size: int = 50,
    sort: str = "last_seen",
    order: str = "desc",
) -> tuple[list[Observable], int]:
    """Query observables with filtering, pagination, and sorting.

    Returns:
        A tuple of ``(items, total_count)``.
    """
    # -- base query ---------------------------------------------------------
    base = select(Observable)
    count_q = select(func.count(Observable.id))

    # -- filters ------------------------------------------------------------
    filters = []

    if q:
        filters.append(Observable.value.ilike(f"%{q}%"))

    if obs_type is not None:
        filters.append(Observable.type == obs_type)

    if confidence_min is not None:
        filters.append(Observable.confidence_score >= confidence_min)

    if last_seen_after is not None:
        filters.append(Observable.last_seen >= last_seen_after)

    if feed_id is not None:
        # Sub-select observable_ids that have a source from the given feed.
        source_sub = (
            select(ObservableSource.observable_id)
            .where(ObservableSource.feed_id == feed_id)
            .correlate(Observable)
            .scalar_subquery()
        )
        filters.append(Observable.id.in_(source_sub))

    if manual_only:
        # Observables with NO sources (manually added).
        has_source = (
            select(ObservableSource.id)
            .where(ObservableSource.observable_id == Observable.id)
            .correlate(Observable)
            .exists()
        )
        filters.append(~has_source)

    if filters:
        base = base.where(and_(*filters))
        count_q = count_q.where(and_(*filters))

    # -- total count --------------------------------------------------------
    total_result = await db.execute(count_q)
    total_count: int = total_result.scalar_one()

    # -- sorting ------------------------------------------------------------
    sort_column_map = {
        "last_seen": Observable.last_seen,
        "first_seen": Observable.first_seen,
        "confidence_score": Observable.confidence_score,
        "value": Observable.value,
        "type": Observable.type,
        "created_at": Observable.created_at,
    }
    sort_col = sort_column_map.get(sort, Observable.last_seen)
    if order == "asc":
        base = base.order_by(sort_col.asc().nullslast())
    else:
        base = base.order_by(sort_col.desc().nullsfirst())

    # -- pagination ---------------------------------------------------------
    offset = (max(1, page) - 1) * size
    base = base.offset(offset).limit(size)

    # -- eager-load sources -------------------------------------------------
    base = base.options(selectinload(Observable.sources))

    result = await db.execute(base)
    items = list(result.scalars().unique().all())
    return items, total_count


async def get_observable(
    db: AsyncSession, observable_id: uuid.UUID
) -> Observable | None:
    """Get a single observable by ID with sources eagerly loaded."""
    result = await db.execute(
        select(Observable)
        .where(Observable.id == observable_id)
        .options(selectinload(Observable.sources))
    )
    return result.scalar_one_or_none()


async def create_observable(
    db: AsyncSession,
    obs_type: ObservableType,
    value: str,
    confidence_score: int = 75,
) -> tuple[Observable, bool]:
    """Create or update a custom observable.

    On conflict, updates confidence to MAX(existing, provided).

    Returns:
        ``(observable, created)`` where *created* is True for new inserts.
    """
    now = datetime.now(UTC)

    stmt = pg_insert(Observable).values(
        id=uuid.uuid4(),
        type=obs_type,
        value=value,
        confidence_score=confidence_score,
        first_seen=now,
        last_seen=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_observable_type_value",
        set_={
            "confidence_score": func.greatest(
                Observable.__table__.c.confidence_score, stmt.excluded.confidence_score
            ),
            "last_seen": func.greatest(
                Observable.__table__.c.last_seen, stmt.excluded.last_seen
            ),
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.flush()

    result = await db.execute(
        select(Observable)
        .where(Observable.type == obs_type, Observable.value == value)
        .options(selectinload(Observable.sources))
    )
    obs = result.scalar_one()

    # Detect new insert: first_seen will be close to now for new rows.
    first_seen = obs.first_seen.replace(tzinfo=UTC) if obs.first_seen and obs.first_seen.tzinfo is None else obs.first_seen
    created = abs((first_seen - now).total_seconds()) < 2 if first_seen else True
    return obs, created


async def delete_observable(
    db: AsyncSession, observable_id: uuid.UUID
) -> bool:
    """Delete an observable by ID. Returns True if deleted."""
    obs = await db.get(Observable, observable_id)
    if not obs:
        return False
    await db.delete(obs)
    await db.flush()
    return True


async def bulk_upsert_from_feed(
    db: AsyncSession,
    feed: Feed,
    raw_observables: list[RawObservable],
) -> tuple[int, int]:
    """Bulk upsert observables from a feed run.

    Each batch is committed independently so that row locks are released
    between batches.  This prevents deadlocks when multiple feeds ingest
    concurrently with overlapping observables.  Because every statement is
    an idempotent upsert, partial completion is safe — a retry will simply
    re-process already-committed rows as no-op updates.

    Returns:
        ``(total_ingested, new_count)`` -- *total_ingested* is the number of
        rows processed and *new_count* is the number of genuinely new
        observables created.
    """
    if not raw_observables:
        return 0, 0

    now = datetime.now(UTC)
    total_ingested = 0
    new_count = 0

    for batch_start in range(0, len(raw_observables), _BATCH_SIZE):
        batch = raw_observables[batch_start : batch_start + _BATCH_SIZE]

        # Deduplicate by (type, value) within the batch — keep last occurrence.
        seen: dict[tuple[ObservableType, str], RawObservable] = {}
        for raw in batch:
            seen[(raw.type, raw.value)] = raw
        # Sort by (type, value) to ensure all concurrent transactions acquire
        # row locks in the same order, preventing deadlocks on the
        # ON CONFLICT DO UPDATE upsert.
        batch = sorted(seen.values(), key=lambda r: (r.type, r.value))

        for attempt in range(_MAX_RETRIES + 1):
            try:
                # ── Step 1: upsert observables ────────────────────────────
                obs_rows: list[dict] = []
                for raw in batch:
                    obs_rows.append(
                        {
                            "id": uuid.uuid4(),
                            "type": raw.type,
                            "value": raw.value,
                            "confidence_score": compute_source_confidence(raw, feed),
                            "first_seen": raw.first_seen or now,
                            "last_seen": raw.last_seen or now,
                        }
                    )

                stmt = pg_insert(Observable).values(obs_rows)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_observable_type_value",
                    set_={
                        "last_seen": func.greatest(Observable.__table__.c.last_seen, stmt.excluded.last_seen),
                        "updated_at": func.now(),
                    },
                )
                stmt = stmt.returning(Observable.__table__.c.id, Observable.__table__.c.type)

                result = await db.execute(stmt)
                returned_rows = result.all()

                # Build a lookup: (type, value) -> observable_id using
                # tuple comparison to avoid the cartesian-product bug that
                # separate IN clauses would produce.
                type_value_pairs = [(r.type, r.value) for r in batch]
                id_lookup: dict[tuple[ObservableType, str], uuid.UUID] = {}

                lookup_stmt = select(
                    Observable.id, Observable.type, Observable.value
                ).where(
                    tuple_(Observable.type, Observable.value).in_(type_value_pairs)
                )
                lookup_result = await db.execute(lookup_stmt)
                for row in lookup_result.all():
                    id_lookup[(row.type, row.value)] = row.id

                batch_ingested = len(returned_rows)

                # Count new inserts by checking first_seen == now (within tolerance).
                new_in_batch = await db.execute(
                    select(func.count(Observable.id)).where(
                        and_(
                            tuple_(Observable.type, Observable.value).in_(type_value_pairs),
                            Observable.first_seen >= now - timedelta(seconds=5),
                        )
                    )
                )
                new_in_batch_count = new_in_batch.scalar_one()

                # ── Step 2: upsert observable_sources ─────────────────────
                source_rows: list[dict] = []
                for raw in batch:
                    key = (raw.type, raw.value)
                    obs_id = id_lookup.get(key)
                    if obs_id is None:
                        continue
                    source_conf = compute_source_confidence(raw, feed)
                    source_rows.append(
                        {
                            "id": uuid.uuid4(),
                            "observable_id": obs_id,
                            "feed_id": feed.id,
                            "source_confidence": source_conf,
                            "first_seen_by_feed": raw.first_seen or now,
                            "last_seen_by_feed": raw.last_seen or now,
                        }
                    )

                if source_rows:
                    # Sort to match lock ordering and prevent deadlocks.
                    source_rows.sort(key=lambda r: (str(r["observable_id"]), str(r["feed_id"])))
                    src_stmt = pg_insert(ObservableSource).values(source_rows)
                    src_stmt = src_stmt.on_conflict_do_update(
                        constraint="uq_observable_source",
                        set_={
                            "source_confidence": func.greatest(
                                ObservableSource.__table__.c.source_confidence,
                                src_stmt.excluded.source_confidence,
                            ),
                            "last_seen_by_feed": func.greatest(
                                ObservableSource.__table__.c.last_seen_by_feed,
                                src_stmt.excluded.last_seen_by_feed,
                            ),
                        },
                    )
                    await db.execute(src_stmt)

                # ── Step 3: recompute effective confidence for affected observables
                affected_ids = list(id_lookup.values())
                if affected_ids:
                    max_conf_sub = (
                        select(func.max(ObservableSource.source_confidence))
                        .where(ObservableSource.observable_id == Observable.id)
                        .correlate(Observable)
                        .scalar_subquery()
                    )
                    await db.execute(
                        Observable.__table__.update()
                        .where(Observable.__table__.c.id.in_(affected_ids))
                        .values(confidence_score=func.coalesce(max_conf_sub, 50))
                    )

                # Commit per-batch to release row locks so concurrent feeds
                # don't accumulate competing lock sets across batches.
                await db.commit()
                total_ingested += batch_ingested
                new_count += new_in_batch_count
                break

            except OperationalError as e:
                await db.rollback()
                if "deadlock" in str(e).lower() and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Deadlock on batch %d, attempt %d/%d — retrying in %.1fs",
                        batch_start, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

    logger.info(
        "Bulk upsert complete: %d ingested, %d new", total_ingested, new_count
    )
    return total_ingested, new_count


async def get_blocklist(
    db: AsyncSession,
    obs_type: ObservableType,
    confidence_min: int = 70,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
) -> list[str]:
    """Get a plain list of observable values for blocklist export.

    Returns distinct values ordered alphabetically.
    """
    stmt = (
        select(Observable.value)
        .distinct()
        .where(
            Observable.type == obs_type,
            Observable.confidence_score >= confidence_min,
        )
    )

    if max_age_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        stmt = stmt.where(Observable.last_seen >= cutoff)

    if feed_id is not None:
        source_sub = (
            select(ObservableSource.observable_id)
            .where(ObservableSource.feed_id == feed_id)
            .scalar_subquery()
        )
        stmt = stmt.where(Observable.id.in_(source_sub))

    stmt = stmt.order_by(Observable.value)

    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def get_export_json(
    db: AsyncSession,
    obs_type: ObservableType | None = None,
    confidence_min: int = 0,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
    limit: int = 10000,
) -> list[Observable]:
    """Get observables for JSON export with sources eagerly loaded."""
    stmt = (
        select(Observable)
        .where(Observable.confidence_score >= confidence_min)
        .options(selectinload(Observable.sources))
    )

    if obs_type is not None:
        stmt = stmt.where(Observable.type == obs_type)

    if max_age_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        stmt = stmt.where(Observable.last_seen >= cutoff)

    if feed_id is not None:
        source_sub = (
            select(ObservableSource.observable_id)
            .where(ObservableSource.feed_id == feed_id)
            .scalar_subquery()
        )
        stmt = stmt.where(Observable.id.in_(source_sub))

    stmt = stmt.order_by(Observable.last_seen.desc()).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
