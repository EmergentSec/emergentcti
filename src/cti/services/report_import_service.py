"""Analyst-reviewed IOC import from reports (issue #14).

``build_preview`` is read-only. ``import_candidates`` re-extracts the report
server-side and accepts only items that are valid candidates of that
re-extraction, so a client cannot import arbitrary values through it. It
writes in the caller's transaction and never commits.

Report attribution lives on ``report_observables`` (not ``observable_sources``),
so report provenance is never presented as a feed.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cti.models.observable import Observable, ObservableType
from cti.models.report import ReportAttachment, report_observables
from cti.schemas.report import (
    ExtractionCandidate,
    ExtractionCounts,
    ExtractionPreview,
    ExtractionSource,
    ImportedObservable,
    ImportResult,
    SkippedImportItem,
)
from cti.services import allowlist_service, ioc_extraction
from cti.services.confidence import recompute_effective_confidence
from cti.services.tlp import red_observable_ids

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from cti.models.report import Report
    from cti.schemas.report import ImportItem

TEXT_CONTENT_TYPES = frozenset({"text/markdown", "text/plain"})
PDF_CONTENT_TYPE = "application/pdf"
REASON_PDF_UNAVAILABLE = "pdf_text_extraction_unavailable"
REASON_UNSUPPORTED_TYPE = "unsupported_content_type"
NOT_A_CANDIDATE = "not_a_candidate"
# Generic on purpose: it must not say why (TLP) an item was not imported.
NOT_IMPORTABLE = "not_importable"
_QUERY_CHUNK = 500
_MAX_DETAIL_ITEMS = 20

_Key = tuple[ObservableType, str]


class NotACandidateError(ValueError):
    """Some import items are not valid candidates in the report."""

    def __init__(self, items: list[tuple[int, ImportItem]]) -> None:
        self.items = items
        super().__init__(NOT_A_CANDIDATE)

    @property
    def detail(self) -> list[dict[str, Any]]:
        # FastAPI-validation-shaped, so generic clients show ``detail[0].msg``.
        named = ", ".join(f"{item.type} {item.value}" for _, item in self.items[:_MAX_DETAIL_ITEMS])
        more = len(self.items) - _MAX_DETAIL_ITEMS
        suffix = f" (and {more} more)" if more > 0 else ""
        return [
            {
                "type": NOT_A_CANDIDATE,
                "loc": ["body", "items"],
                "msg": (
                    f"{len(self.items)} item(s) are not valid candidates extracted from "
                    f"this report: {named}{suffix}"
                ),
                "items": [
                    {"index": index, "type": item.type, "value": item.value}
                    for index, item in self.items
                ],
            }
        ]


@dataclass
class _Extraction:
    sources: list[ExtractionSource]
    result: ioc_extraction.ExtractionResult


def _utcnow() -> datetime:
    # Report and observable timestamps are timezone-naive UTC columns.
    return datetime.now(UTC).replace(tzinfo=None)


async def _extract_report(db: AsyncSession, report: Report) -> _Extraction:
    sources: list[ExtractionSource] = []
    texts: list[str] = []

    content = report.content or ""
    has_content = bool(content.strip())
    sources.append(
        ExtractionSource(
            kind="content",
            filename=None,
            content_type=None,
            status="extracted" if has_content else "empty",
            reason=None,
        )
    )
    if has_content:
        texts.append(content)

    attachment = report.attachment
    if attachment is not None:
        status: str
        reason: str | None = None
        if attachment.content_type in TEXT_CONTENT_TYPES:
            data = await db.scalar(
                select(ReportAttachment.content).where(ReportAttachment.id == attachment.id)
            )
            # Validated as UTF-8 on upload; replace defensively rather than fail.
            text = (data or b"").decode("utf-8", errors="replace")
            if text.strip():
                status = "extracted"
                texts.append(text)
            else:
                status = "empty"
        elif attachment.content_type == PDF_CONTENT_TYPE:
            status, reason = "unsupported", REASON_PDF_UNAVAILABLE
        else:
            status, reason = "unsupported", REASON_UNSUPPORTED_TYPE
        sources.append(
            ExtractionSource(
                kind="attachment",
                filename=attachment.original_filename,
                content_type=attachment.content_type,
                status=status,
                reason=reason,
            )
        )

    return _Extraction(sources=sources, result=ioc_extraction.extract(texts))


def _chunks(values: Sequence[str]) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), _QUERY_CHUNK):
        yield values[start : start + _QUERY_CHUNK]


async def _find_observables(
    db: AsyncSession,
    keys: Iterable[_Key],
) -> dict[_Key, tuple[uuid.UUID, int]]:
    by_type: dict[ObservableType, list[str]] = defaultdict(list)
    for obs_type, value in keys:
        by_type[obs_type].append(value)
    found: dict[_Key, tuple[uuid.UUID, int]] = {}
    for obs_type, values in by_type.items():
        for chunk in _chunks(values):
            rows = await db.execute(
                select(Observable.id, Observable.value, Observable.confidence_score).where(
                    Observable.type == obs_type,
                    Observable.value.in_(chunk),
                )
            )
            for observable_id, value, confidence in rows:
                found[(obs_type, value)] = (observable_id, confidence)
    return found


async def _find_links(
    db: AsyncSession,
    report_id: uuid.UUID,
    observable_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, datetime | None]:
    """Existing link rows for this report: observable id → imported_at."""
    links: dict[uuid.UUID, datetime | None] = {}
    for start in range(0, len(observable_ids), _QUERY_CHUNK):
        chunk = observable_ids[start : start + _QUERY_CHUNK]
        rows = await db.execute(
            select(report_observables.c.observable_id, report_observables.c.imported_at).where(
                report_observables.c.report_id == report_id,
                report_observables.c.observable_id.in_(chunk),
            )
        )
        for observable_id, imported_at in rows:
            links[observable_id] = imported_at
    return links


async def build_preview(
    db: AsyncSession, report: Report, *, hide_red: bool = False
) -> ExtractionPreview:
    """Extract candidates and flag them against current data. Never writes.

    With *hide_red* (API-key callers), effective-RED observables are treated
    as if they did not exist, so the preview is the same as for a new value.
    """
    extraction = await _extract_report(db, report)
    candidates = extraction.result.candidates

    valid_keys = [(c.type, c.value) for c in candidates if c.valid]
    existing = await _find_observables(db, valid_keys)
    if hide_red and existing:
        red = await red_observable_ids(db, (oid for oid, _ in existing.values()))
        existing = {key: match for key, match in existing.items() if match[0] not in red}
    existing_ids = [observable_id for observable_id, _ in existing.values()]
    links = await _find_links(db, report.id, existing_ids)

    entries = await allowlist_service.list_entries(db)
    matcher = allowlist_service.AllowlistMatcher(entries)
    entry_values = {entry.id: entry.value for entry in entries}

    items: list[ExtractionCandidate] = []
    counts = {"new": 0, "existing": 0, "invalid": 0}
    for candidate in candidates:
        key = (candidate.type, candidate.value)
        match = existing.get(key) if candidate.valid else None
        status = "invalid" if not candidate.valid else ("existing" if match else "new")
        counts[status] += 1
        allowlist_matches: list[str] = []
        if candidate.valid:
            allowlist_matches = sorted({entry_values[entry_id] for entry_id in matcher.match(*key)})
        items.append(
            ExtractionCandidate(
                type=candidate.type.value,
                value=candidate.value,
                original=candidate.original,
                context=candidate.context,
                occurrences=candidate.occurrences,
                defanged=candidate.defanged,
                status=status,
                existing_observable_id=match[0] if match else None,
                existing_confidence=match[1] if match else None,
                already_attributed=match is not None and match[0] in links,
                allowlisted=bool(allowlist_matches),
                allowlist_matches=allowlist_matches,
                warnings=candidate.warnings,
            )
        )

    return ExtractionPreview(
        report_id=report.id,
        sources=extraction.sources,
        candidates=items,
        truncated=extraction.result.truncated,
        counts=ExtractionCounts(total=len(items), **counts),
    )


def _dialect_insert(db: AsyncSession) -> Any:
    return pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert


async def import_candidates(
    db: AsyncSession,
    report: Report,
    *,
    confidence: int,
    items: Sequence[ImportItem],
    imported_by_id: uuid.UUID | None,
    hide_red: bool = False,
) -> ImportResult:
    """Import reviewed candidates. Validates everything before writing.

    With *hide_red* (API-key callers), items whose existing observable is
    effective-RED are skipped untouched (no link, no confidence change) and
    reported in ``skipped`` with the generic reason ``not_importable``. Every
    counter covers only the imported items.

    Raises:
        NotACandidateError: an item is not a valid candidate of the report as
            re-extracted now. Nothing has been written.
    """
    extraction = await _extract_report(db, report)
    candidates = {(c.type.value, c.value): c for c in extraction.result.candidates if c.valid}
    offending = [
        (index, item)
        for index, item in enumerate(items)
        if (item.type, item.value) not in candidates
    ]
    if offending:
        raise NotACandidateError(offending)

    now = _utcnow()
    keys: list[_Key] = [(ObservableType(item.type), item.value) for item in items]
    insert = _dialect_insert(db)

    # Observable upsert on the (type, value) unique key: insert only what is
    # missing, never touching existing rows. Pre-generated ids tell which rows
    # this request created, even if a concurrent writer won a race.
    observables = await _find_observables(db, keys)
    proposed_ids: dict[_Key, uuid.UUID] = {}
    missing = [key for key in keys if key not in observables]
    if missing:
        rows = []
        for key in missing:
            proposed_ids[key] = uuid.uuid4()
            rows.append(
                {
                    "id": proposed_ids[key],
                    "type": key[0],
                    "value": key[1],
                    "confidence_score": confidence,
                    "first_seen": now,
                    "last_seen": now,
                }
            )
        await db.execute(
            insert(Observable).values(rows).on_conflict_do_nothing(index_elements=["type", "value"])
        )
        observables.update(await _find_observables(db, missing))

    skipped: list[SkippedImportItem] = []
    if hide_red:
        # Checked after the upsert so a RED row created concurrently is caught too.
        red = await red_observable_ids(db, (observables[key][0] for key in keys))
        skipped = [
            SkippedImportItem(type=key[0].value, value=key[1], reason=NOT_IMPORTABLE)
            for key in keys
            if observables[key][0] in red
        ]
        keys = [key for key in keys if observables[key][0] not in red]

    links = await _find_links(db, report.id, [observables[key][0] for key in keys])
    attribution = {
        "imported_at": now,
        "imported_by_id": imported_by_id,
        "analyst_confidence": confidence,
    }
    excerpts = {
        observables[key][0]: candidates[(key[0].value, key[1])].context[:500] for key in keys
    }

    # Counters come from what the database reports it changed, not from the
    # snapshot read above: a concurrent import can win any of these writes.
    attributed: set[uuid.UUID] = set()
    to_fill = [oid for oid, imported_at in links.items() if imported_at is None]
    new_link_ids = [observables[key][0] for key in keys if observables[key][0] not in links]
    if new_link_ids:
        inserted = await db.execute(
            insert(report_observables)
            .values(
                [
                    {
                        "report_id": report.id,
                        "observable_id": observable_id,
                        "source_excerpt": excerpts[observable_id],
                        **attribution,
                    }
                    for observable_id in new_link_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["report_id", "observable_id"])
            .returning(report_observables.c.observable_id)
        )
        attributed.update(inserted.scalars())
        # Lost the insert race: the winner's row may be a manual link to fill.
        to_fill.extend(oid for oid in new_link_ids if oid not in attributed)
    for observable_id in to_fill:
        # Manual link from #12: fill in attribution, keep the row.
        filled = await db.execute(
            update(report_observables)
            .where(
                report_observables.c.report_id == report.id,
                report_observables.c.observable_id == observable_id,
                report_observables.c.imported_at.is_(None),
            )
            .values(source_excerpt=excerpts[observable_id], **attribution)
            .returning(report_observables.c.observable_id)
        )
        if filled.first() is not None:  # Zero rows: a concurrent import filled it.
            attributed.add(observable_id)

    imported_ids = [observables[key][0] for key in keys]
    await recompute_effective_confidence(db, imported_ids)
    observables = await _find_observables(db, keys)

    created = attributed_existing = already_attributed = 0
    result_observables: list[ImportedObservable] = []
    for key in keys:
        observable_id, confidence_score = observables[key]
        was_created = proposed_ids.get(key) == observable_id
        if observable_id not in attributed:
            already_attributed += 1
        elif was_created:
            created += 1
        else:
            attributed_existing += 1
        result_observables.append(
            ImportedObservable(
                id=observable_id,
                type=key[0].value,
                value=key[1],
                confidence_score=confidence_score,
                created=was_created,
            )
        )

    await db.flush()
    # The report's eagerly loaded observable list predates these writes.
    db.expire(report, ["observables"])

    return ImportResult(
        created=created,
        attributed_existing=attributed_existing,
        already_attributed=already_attributed,
        observables=result_observables,
        skipped=skipped,
    )
