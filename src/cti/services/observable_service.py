"""Observable CRUD, bulk upsert, and blocklist/export query service."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, case, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import selectinload

from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.models.tag import Tag, observable_tags
from cti.services import allowlist_service
from cti.services.confidence import compute_source_confidence, recompute_effective_confidence
from cti.services.tlp import (
    MARKING_KEYS,
    effective_tlp_expr,
    marking_key,
    shareable_clause,
    tlp_filter,
    tlp_rank_expr,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from cti.feeds.base import RawObservable
    from cti.models.feed import Feed
    from cti.models.tlp import Tlp
    from cti.services.allowlist_service import AllowlistMatcher

logger = logging.getLogger(__name__)

# Maximum rows per INSERT batch to avoid excessive memory usage.
_BATCH_SIZE = 500

# Deadlock retry parameters.
_MAX_RETRIES = 3
_BASE_DELAY = 0.5  # seconds

# Candidate rows buffered per fetch while streaming an export through the allowlist.
_EXPORT_PAGE_SIZE = 2000


async def get_observables(
    db: AsyncSession,
    q: str | None = None,
    obs_type: ObservableType | None = None,
    confidence_min: int | None = None,
    feed_id: uuid.UUID | None = None,
    manual_only: bool = False,
    last_seen_after: datetime | None = None,
    tags: Sequence[str] | None = None,
    tlp: Sequence[str] | None = None,
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

    if tags:
        filters.append(_tag_filter(tags))

    if tlp:
        filters.append(tlp_filter(effective_tlp_expr(), tlp))

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

    # -- eager-load response relationships ---------------------------------
    base = base.options(
        selectinload(Observable.sources),
        selectinload(Observable.override_set_by),
    )

    result = await db.execute(base)
    items = list(result.scalars().unique().all())
    return items, total_count


def _tag_filter(tag_names: Sequence[str]):  # type: ignore[no-untyped-def]
    """Observable has ANY of the (already normalized) tag names."""
    tagged = (
        select(observable_tags.c.observable_id)
        .join(Tag, Tag.id == observable_tags.c.tag_id)
        .where(Tag.name.in_(list(tag_names)))
    )
    return Observable.id.in_(tagged)


async def get_observable(db: AsyncSession, observable_id: uuid.UUID) -> Observable | None:
    """Get a single observable by ID with sources eagerly loaded."""
    result = await db.execute(
        select(Observable)
        .where(Observable.id == observable_id)
        .options(
            selectinload(Observable.sources),
            selectinload(Observable.override_set_by),
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_observable(
    db: AsyncSession,
    obs_type: ObservableType,
    value: str,
    confidence_score: int = 75,
    tlp: Tlp | None = None,
) -> tuple[Observable, bool]:
    """Create or update a custom observable.

    On conflict, updates confidence to MAX(existing, provided) and keeps the
    more restrictive manual TLP marking (a specified value replaces NULL,
    never the reverse).

    Returns:
        ``(observable, created)`` where *created* is True for new inserts.
    """
    now = datetime.now(UTC)

    stmt = pg_insert(Observable).values(
        id=uuid.uuid4(),
        type=obs_type,
        value=value,
        confidence_score=confidence_score,
        manual_confidence=confidence_score,
        manual_tlp=tlp.value if tlp is not None else None,
        first_seen=now,
        last_seen=now,
    )
    existing_tlp = Observable.__table__.c.manual_tlp
    new_tlp = stmt.excluded.manual_tlp
    stmt = stmt.on_conflict_do_update(
        constraint="uq_observable_type_value",
        set_={
            "manual_confidence": func.greatest(
                Observable.__table__.c.manual_confidence,
                stmt.excluded.manual_confidence,
            ),
            "manual_tlp": case(
                (new_tlp.is_(None), existing_tlp),
                (existing_tlp.is_(None), new_tlp),
                (tlp_rank_expr(new_tlp) > tlp_rank_expr(existing_tlp), new_tlp),
                else_=existing_tlp,
            ),
            "last_seen": func.greatest(Observable.__table__.c.last_seen, stmt.excluded.last_seen),
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.flush()

    result = await db.execute(
        select(Observable)
        .where(Observable.type == obs_type, Observable.value == value)
        .options(
            selectinload(Observable.sources),
            selectinload(Observable.override_set_by),
        )
        .execution_options(populate_existing=True)
    )
    obs = result.scalar_one()
    await recompute_effective_confidence(db, [obs.id])
    await db.flush()
    obs = await get_observable(db, obs.id)
    assert obs is not None

    # Detect new insert: first_seen will be close to now for new rows.
    first_seen = (
        obs.first_seen.replace(tzinfo=UTC)
        if obs.first_seen and obs.first_seen.tzinfo is None
        else obs.first_seen
    )
    created = abs((first_seen - now).total_seconds()) < 2 if first_seen else True
    return obs, created


async def delete_observable(db: AsyncSession, observable_id: uuid.UUID) -> bool:
    """Delete an observable by ID. Returns True if deleted."""
    obs = await db.get(Observable, observable_id)
    if not obs:
        return False
    await db.delete(obs)
    await db.flush()
    return True


async def set_confidence_override(
    db: AsyncSession,
    observable_id: uuid.UUID,
    confidence: int,
    *,
    set_by_id: uuid.UUID | None,
) -> Observable | None:
    """Pin an observable's effective confidence to an exact value."""
    obs = await get_observable(db, observable_id)
    if obs is None:
        return None
    obs.confidence_override = confidence
    obs.override_set_at = datetime.now(UTC)
    obs.override_set_by_id = set_by_id
    await recompute_effective_confidence(db, [observable_id])
    await db.flush()
    return await get_observable(db, observable_id)


async def clear_confidence_override(
    db: AsyncSession,
    observable_id: uuid.UUID,
) -> Observable | None:
    """Clear a pinned confidence and restore the feed/analyst floor rule."""
    obs = await get_observable(db, observable_id)
    if obs is None:
        return None
    obs.confidence_override = None
    obs.override_set_at = None
    obs.override_set_by_id = None
    await recompute_effective_confidence(db, [observable_id])
    await db.flush()
    return await get_observable(db, observable_id)


async def set_tlp_override(
    db: AsyncSession,
    observable_id: uuid.UUID,
    tlp: Tlp,
    reason: str,
    *,
    set_by_id: uuid.UUID | None,
) -> Observable | None:
    """Reclassify an observable: its effective marking becomes *tlp*."""
    obs = await get_observable(db, observable_id)
    if obs is None:
        return None
    obs.tlp_override = tlp.value
    obs.tlp_override_reason = reason
    obs.tlp_override_set_at = datetime.now(UTC)
    obs.tlp_override_set_by_id = set_by_id
    await db.flush()
    logger.info(
        "TLP override on observable %s set to %s; reason: %s", observable_id, tlp.value, reason
    )
    return await get_observable(db, observable_id)


async def clear_tlp_override(db: AsyncSession, observable_id: uuid.UUID) -> Observable | None:
    """Remove a reclassification; the input-derived marking applies again."""
    obs = await get_observable(db, observable_id)
    if obs is None:
        return None
    if obs.tlp_override is not None:
        logger.info("TLP override on observable %s cleared", observable_id)
    obs.tlp_override = None
    obs.tlp_override_reason = None
    obs.tlp_override_set_at = None
    obs.tlp_override_set_by_id = None
    await db.flush()
    return await get_observable(db, observable_id)


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
                        "last_seen": func.greatest(
                            Observable.__table__.c.last_seen,
                            stmt.excluded.last_seen,
                        ),
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

                lookup_stmt = select(Observable.id, Observable.type, Observable.value).where(
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
                            "native_confidence": source_conf,
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
                            "native_confidence": func.greatest(
                                ObservableSource.__table__.c.native_confidence,
                                src_stmt.excluded.native_confidence,
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
                    await recompute_effective_confidence(db, affected_ids)

                # Commit per-batch to release row locks so concurrent feeds
                # don't accumulate competing lock sets across batches.
                await db.commit()
                total_ingested += batch_ingested
                new_count += new_in_batch_count
                break

            except OperationalError as e:
                await db.rollback()
                if "deadlock" in str(e).lower() and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Deadlock on batch %d, attempt %d/%d — retrying in %.1fs",
                        batch_start,
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

    logger.info("Bulk upsert complete: %d ingested, %d new", total_ingested, new_count)
    return total_ingested, new_count


# C0/C1 control characters plus the Unicode line/paragraph separators: anything a
# line-oriented consumer could treat as a record break.
_LINE_UNSAFE = re.compile("[\\x00-\\x1f\\x7f-\\x9f\\u2028\\u2029]")


def is_line_safe(value: str) -> bool:
    """Whether a value can be emitted as exactly one line of a text export.

    A value such as ``"evil.test\\n10.0.0.5"`` would otherwise smuggle a second
    indicator past the allowlist, which is only ever evaluated against the
    whole stored value. Such values are omitted from text formats (JSON exports
    keep them verbatim, safely escaped).
    """
    return _LINE_UNSAFE.search(value) is None


def _export_filters(
    obs_type: ObservableType | None,
    confidence_min: int,
    max_age_days: int | None,
    feed_id: uuid.UUID | None,
    tags: Sequence[str] | None = None,
) -> list:
    """WHERE clauses shared by every export query (TLP is applied separately)."""
    filters = [Observable.confidence_score >= confidence_min]

    if tags:
        filters.append(_tag_filter(tags))

    if obs_type is not None:
        filters.append(Observable.type == obs_type)

    if max_age_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        filters.append(Observable.last_seen >= cutoff)

    if feed_id is not None:
        source_sub = (
            select(ObservableSource.observable_id)
            .where(ObservableSource.feed_id == feed_id)
            .scalar_subquery()
        )
        filters.append(Observable.id.in_(source_sub))

    return filters


async def get_blocklist(
    db: AsyncSession,
    obs_type: ObservableType,
    confidence_min: int = 70,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
    tags: Sequence[str] | None = None,
    *,
    apply_allowlist: bool = True,
) -> list[str]:
    """Get a plain list of observable values for blocklist export.

    Returns distinct values ordered alphabetically, with currently allowlisted
    and TLP-withheld (``internal`` destination) values removed. Values that are
    not line-safe are always omitted, so the pre-policy list is safe to join
    and cache. Pass ``apply_allowlist=False`` only to obtain the *pre-policy*
    list (neither allowlist nor TLP applied) for caching; the caller must then
    filter it with :func:`apply_blocklist_policy` before serving it.
    """
    stmt = (
        select(Observable.value)
        .distinct()
        .where(*_export_filters(obs_type, confidence_min, max_age_days, feed_id, tags))
        .order_by(Observable.value)
    )

    result = await db.execute(stmt)
    values = [row[0] for row in result.all() if is_line_safe(row[0])]
    if not apply_allowlist:
        return values
    served, _withheld = await apply_blocklist_policy(
        db,
        values,
        obs_type=obs_type,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        feed_id=feed_id,
        tags=tags,
    )
    return served


async def apply_blocklist_policy(
    db: AsyncSession,
    candidates: Sequence[str],
    *,
    obs_type: ObservableType,
    confidence_min: int,
    max_age_days: int | None,
    feed_id: uuid.UUID | None,
    tags: Sequence[str] | None,
    destination: str = "internal",
    allowlist: AllowlistMatcher | None = None,
) -> tuple[list[str], int]:
    """Apply the *current* allowlist and TLP policy to a pre-policy blocklist.

    Safe for cached candidates: markings are read from the database on every
    call, so a new RED marking or override is honored on the next request.

    Returns ``(values, tlp_withheld)`` where *tlp_withheld* counts candidates
    that pass the allowlist but are withheld by TLP.
    """
    matcher = allowlist if allowlist is not None else await allowlist_service.load_matcher(db)
    filters = _export_filters(obs_type, confidence_min, max_age_days, feed_id, tags)
    # (type, value) is unique, so within one type a value is one observable.
    blocked = {value async for _type, value, _marking in _stream_withheld(db, filters, destination)}
    values: list[str] = []
    withheld = 0
    for value in candidates:
        if matcher.is_allowlisted(obs_type, value):
            continue
        if value in blocked:
            withheld += 1
            continue
        values.append(value)
    return values, withheld


async def _stream_export_candidates(
    db: AsyncSession,
    filters: list,
    order_by: tuple,
) -> AsyncIterator[tuple[uuid.UUID, ObservableType, str]]:
    """Yield lightweight ``(id, type, value)`` rows for allowlist filtering.

    Streams in batches so a large export never holds full ORM rows (or their
    sources) in memory just to decide what the policy suppresses.
    """
    stmt = (
        select(Observable.id, Observable.type, Observable.value)
        .where(*filters)
        .order_by(*order_by)
        .execution_options(yield_per=_EXPORT_PAGE_SIZE)
    )
    result = await db.stream(stmt)
    try:
        async for row in result:
            yield row.id, row.type, row.value
    finally:
        await result.close()


async def _stream_withheld(
    db: AsyncSession,
    filters: list,
    destination: str,
) -> AsyncIterator[tuple[ObservableType, str, str | None]]:
    """Yield ``(type, value, effective_marking)`` for rows TLP withholds."""
    effective = effective_tlp_expr()
    stmt = (
        select(Observable.type, Observable.value, effective)
        .where(*filters, ~shareable_clause(effective, destination))
        .execution_options(yield_per=_EXPORT_PAGE_SIZE)
    )
    result = await db.stream(stmt)
    try:
        async for row in result:
            yield row[0], row[1], row[2]
    finally:
        await result.close()


def _empty_marking_counts() -> dict[str, int]:
    return dict.fromkeys(MARKING_KEYS, 0)


async def _withheld_counts(
    db: AsyncSession,
    filters: list,
    destination: str,
    matcher: AllowlistMatcher,
    *,
    line_safe: bool,
) -> tuple[int, dict[str, int]]:
    """Classify the rows TLP withholds: ``(allowlisted, by_marking)``.

    Allowlisted rows are reported as allowlist exclusions (the allowlist is
    independent of TLP); only rows that pass the allowlist count against TLP.
    """
    allowlisted = 0
    by_marking = _empty_marking_counts()
    async with aclosing(_stream_withheld(db, filters, destination)) as rows:
        async for row_type, value, marking in rows:
            if line_safe and not is_line_safe(value):
                continue
            if matcher.is_allowlisted(row_type, value):
                allowlisted += 1
                continue
            by_marking[marking_key(marking)] += 1
    return allowlisted, by_marking


async def count_tlp_excluded(
    db: AsyncSession,
    obs_type: ObservableType | None = None,
    confidence_min: int = 0,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
    tags: Sequence[str] | None = None,
    *,
    destination: str = "internal",
    line_safe: bool = False,
    allowlist: AllowlistMatcher | None = None,
) -> dict[str, int]:
    """Rows matching the filters and the allowlist that TLP withholds, by marking."""
    matcher = allowlist if allowlist is not None else await allowlist_service.load_matcher(db)
    filters = _export_filters(obs_type, confidence_min, max_age_days, feed_id, tags)
    _allowlisted, by_marking = await _withheld_counts(
        db, filters, destination, matcher, line_safe=line_safe
    )
    return by_marking


async def get_export_values(
    db: AsyncSession,
    obs_type: ObservableType | None = None,
    confidence_min: int = 0,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
    tags: Sequence[str] | None = None,
    *,
    destination: str = "internal",
    order: str = "recent",
    line_safe: bool = False,
    allowlist: AllowlistMatcher | None = None,
) -> tuple[list[str], int, dict[str, int]]:
    """Get every exportable value matching the filters, without a row limit.

    ``order`` is ``"recent"`` (newest ``last_seen`` first, the JSON/text export
    order) or ``"value"`` (alphabetical, deduplicated — the blocklist order).
    Pass ``line_safe=True`` whenever the values will be written one per line:
    values containing control characters or line breaks are then omitted.

    Returns:
        ``(values, excluded_allowlisted, excluded_by_tlp)``: the number of
        observables that matched the filters but were suppressed by the
        current allowlist, and — per effective marking — those that pass the
        allowlist but may not leave to *destination*.
    """
    matcher = allowlist if allowlist is not None else await allowlist_service.load_matcher(db)

    filters = _export_filters(obs_type, confidence_min, max_age_days, feed_id, tags)
    shareable = shareable_clause(effective_tlp_expr(), destination)
    if order == "value":
        order_by = (Observable.value, Observable.id)
    else:
        order_by = (Observable.last_seen.desc(), Observable.id)

    values: list[str] = []
    excluded = 0
    seen: set[str] = set()
    async with aclosing(
        _stream_export_candidates(db, [*filters, shareable], order_by)
    ) as candidates:
        async for _id, row_type, value in candidates:
            if line_safe and not is_line_safe(value):
                continue
            if matcher.is_allowlisted(row_type, value):
                excluded += 1
                continue
            if order == "value":
                if value in seen:
                    continue
                seen.add(value)
            values.append(value)

    withheld_allowlisted, by_marking = await _withheld_counts(
        db, filters, destination, matcher, line_safe=line_safe
    )
    return values, excluded + withheld_allowlisted, by_marking


async def get_export_json(
    db: AsyncSession,
    obs_type: ObservableType | None = None,
    confidence_min: int = 0,
    max_age_days: int | None = None,
    feed_id: uuid.UUID | None = None,
    limit: int | None = 10000,
    tags: Sequence[str] | None = None,
    *,
    destination: str = "internal",
    allowlist: AllowlistMatcher | None = None,
) -> list[Observable]:
    """Get observables for JSON export with sources eagerly loaded.

    Allowlisted and TLP-withheld observables are excluded *before* ``limit``
    is applied, so a limited export is never short-changed by suppressed
    rows. ``limit=None`` returns every eligible observable.
    """
    matcher = allowlist if allowlist is not None else await allowlist_service.load_matcher(db)

    filters = _export_filters(obs_type, confidence_min, max_age_days, feed_id, tags)
    filters.append(shareable_clause(effective_tlp_expr(), destination))
    # id breaks last_seen ties so the export order is deterministic.
    order_by = (Observable.last_seen.desc(), Observable.id)

    # Pass 1: pick the exported ids from lightweight rows, stopping at the limit.
    selected: list[uuid.UUID] = []
    if limit is None or limit > 0:
        # aclosing releases the cursor before pass 2 even when we stop early.
        async with aclosing(_stream_export_candidates(db, filters, order_by)) as candidates:
            async for obs_id, row_type, value in candidates:
                if matcher.is_allowlisted(row_type, value):
                    continue
                selected.append(obs_id)
                if limit is not None and len(selected) >= limit:
                    break

    # Pass 2: load only the selected observables (with sources), in export order.
    observables: list[Observable] = []
    for start in range(0, len(selected), _BATCH_SIZE):
        chunk = selected[start : start + _BATCH_SIZE]
        result = await db.execute(
            select(Observable)
            .where(Observable.id.in_(chunk))
            .options(selectinload(Observable.sources))
        )
        by_id = {obs.id: obs for obs in result.scalars().unique().all()}
        # A row deleted between the passes is simply skipped.
        observables.extend(by_id[i] for i in chunk if i in by_id)
    return observables
