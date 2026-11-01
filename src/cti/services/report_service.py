from __future__ import annotations

import hashlib
import unicodedata
from datetime import datetime, time, timedelta
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import selectinload, undefer

from cti.models.observable import Observable
from cti.models.report import Report, ReportAttachment, report_observables
from cti.models.tag import Tag, report_tags
from cti.services import tlp as tlp_policy
from cti.services.confidence import recompute_effective_confidence

if TYPE_CHECKING:
    import uuid

    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.base import ExecutableOption

    from cti.schemas.report import ReportCreate, ReportFilters, ReportUpdate

_UPLOAD_CHUNK_BYTES = 64 * 1024
_ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}


class ReportValidationError(ValueError):
    pass


class EmptyUploadError(ValueError):
    pass


class UnsupportedUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


def _load_options() -> tuple[ExecutableOption, ...]:
    return (
        selectinload(Report.created_by),
        selectinload(Report.attachment),
        selectinload(Report.observables),
        selectinload(Report.tags),
    )


async def list_reports(
    db: AsyncSession,
    filters: ReportFilters,
) -> tuple[list[Report], int]:
    clauses = []
    if filters.q:
        escaped = filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        clauses.append(
            or_(
                Report.title.ilike(pattern, escape="\\"),
                Report.summary.ilike(pattern, escape="\\"),
            )
        )
    if filters.origin is not None:
        clauses.append(Report.origin == filters.origin)
    if filters.source_name is not None:
        clauses.append(Report.source_name == filters.source_name)
    if filters.published_from is not None:
        clauses.append(Report.published_at >= datetime.combine(filters.published_from, time.min))
    if filters.published_to is not None:
        exclusive_end = datetime.combine(filters.published_to, time.min) + timedelta(days=1)
        clauses.append(Report.published_at < exclusive_end)
    if filters.ai_generated is not None:
        clauses.append(Report.is_ai_generated == filters.ai_generated)
    if filters.tags:
        tagged = (
            select(report_tags.c.report_id)
            .join(Tag, Tag.id == report_tags.c.tag_id)
            .where(Tag.name.in_(filters.tags))
        )
        clauses.append(Report.id.in_(tagged))
    if filters.tlp:
        clauses.append(tlp_policy.tlp_filter(Report.tlp, filters.tlp))
    if filters.exclude_red:
        clauses.append(tlp_policy.not_red_clause(Report.tlp))

    count_query = select(func.count(Report.id)).where(*clauses)
    total = await db.scalar(count_query) or 0

    query = (
        select(Report)
        .where(*clauses)
        .options(*_load_options())
        .order_by(Report.published_at.desc().nulls_last(), Report.created_at.desc())
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
    )
    reports = list((await db.scalars(query)).unique().all())
    return reports, total


async def list_sources(db: AsyncSession) -> list[str]:
    query = (
        select(Report.source_name)
        .where(Report.source_name.is_not(None))
        .distinct()
        .order_by(Report.source_name)
    )
    return [source for source in (await db.scalars(query)).all() if source is not None]


async def get_report(
    db: AsyncSession, report_id: uuid.UUID, *, refresh: bool = False
) -> Report | None:
    query = select(Report).where(Report.id == report_id).options(*_load_options())
    if refresh:
        query = query.execution_options(populate_existing=True)
    return (await db.scalars(query)).unique().one_or_none()


async def create_report(
    db: AsyncSession,
    data: ReportCreate,
    *,
    created_by_id: uuid.UUID | None,
) -> Report:
    values = data.model_dump()
    if values.get("tlp") is not None:
        values["tlp"] = values["tlp"].value
    report = Report(**values, created_by_id=created_by_id)
    db.add(report)
    await db.flush()
    result = await get_report(db, report.id)
    assert result is not None
    return result


def _validate_merged_ai_provenance(report: Report, updates: dict[str, object]) -> None:
    is_ai_generated = updates.get("is_ai_generated", report.is_ai_generated)
    provenance = (
        updates.get("ai_provider", report.ai_provider),
        updates.get("ai_model", report.ai_model),
        updates.get("ai_generated_at", report.ai_generated_at),
    )
    if not is_ai_generated and any(value is not None for value in provenance):
        raise ReportValidationError("ai_* fields require is_ai_generated=true")


async def update_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    data: ReportUpdate,
) -> Report | None:
    report = await get_report(db, report_id)
    if report is None:
        return None
    updates = data.model_dump(exclude_unset=True)
    reason = updates.pop("tlp_change_reason", None)
    if "tlp" in updates:
        new_tlp = updates["tlp"].value if updates["tlp"] is not None else None
        updates["tlp"] = new_tlp
        try:
            tlp_policy.check_marking_change("report", report.id, report.tlp, new_tlp, reason)
        except tlp_policy.TlpDowngradeReasonRequiredError as exc:
            raise ReportValidationError(str(exc)) from None
    _validate_merged_ai_provenance(report, updates)
    for field, value in updates.items():
        setattr(report, field, value)
    await db.flush()
    await db.refresh(report)
    return await get_report(db, report_id)


async def delete_report(db: AsyncSession, report_id: uuid.UUID) -> bool:
    if await db.get(Report, report_id) is None:
        return False
    observable_ids = list(
        await db.scalars(
            select(report_observables.c.observable_id).where(
                report_observables.c.report_id == report_id
            )
        )
    )
    # Explicit child deletion keeps SQLite tests correct when FK enforcement is off.
    await db.execute(delete(report_observables).where(report_observables.c.report_id == report_id))
    await db.execute(delete(report_tags).where(report_tags.c.report_id == report_id))
    await db.execute(delete(ReportAttachment).where(ReportAttachment.report_id == report_id))
    await db.execute(delete(Report).where(Report.id == report_id))
    await recompute_effective_confidence(db, observable_ids)
    await db.flush()
    return True


def sanitize_filename(filename: str) -> str:
    decoded = unquote(filename)
    basename = PurePosixPath(decoded.replace("\\", "/")).name
    basename = "".join(ch for ch in basename if unicodedata.category(ch) != "Cc")
    return basename[:255]


async def read_and_validate_upload(
    file: UploadFile,
    max_bytes: int,
) -> tuple[str, str, bytes]:
    filename = sanitize_filename(file.filename or "")
    extension = PurePosixPath(filename).suffix.lower()
    content_type = _ALLOWED_EXTENSIONS.get(extension)
    if content_type is None:
        raise UnsupportedUploadError("Unsupported attachment type")

    content = bytearray()
    while True:
        remaining = max_bytes + 1 - len(content)
        chunk = await file.read(min(_UPLOAD_CHUNK_BYTES, remaining))
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > max_bytes:
            raise UploadTooLargeError("Attachment exceeds the upload size limit")

    if not content:
        raise EmptyUploadError("Attachment must not be empty")

    data = bytes(content)
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise UnsupportedUploadError("PDF attachment does not have a valid PDF signature")
    else:
        if b"\x00" in data:
            raise UnsupportedUploadError("Text attachment must not contain NUL bytes")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise UnsupportedUploadError("Text attachment must be valid UTF-8") from None

    return filename, content_type, data


async def replace_attachment(
    db: AsyncSession,
    report_id: uuid.UUID,
    *,
    original_filename: str,
    content_type: str,
    content: bytes,
) -> ReportAttachment | None:
    if await db.get(Report, report_id) is None:
        return None
    existing = await db.scalar(
        select(ReportAttachment).where(ReportAttachment.report_id == report_id)
    )
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    attachment = ReportAttachment(
        report_id=report_id,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def delete_attachment(db: AsyncSession, report_id: uuid.UUID) -> bool:
    attachment = await db.scalar(
        select(ReportAttachment).where(ReportAttachment.report_id == report_id)
    )
    if attachment is None:
        return False
    await db.delete(attachment)
    await db.flush()
    return True


async def get_report_tlp(db: AsyncSession, report_id: uuid.UUID) -> str | None:
    """The report's own marking (the attachment inherits it)."""
    return await db.scalar(select(Report.tlp).where(Report.id == report_id))


async def get_attachment_for_download(
    db: AsyncSession,
    report_id: uuid.UUID,
) -> ReportAttachment | None:
    query = (
        select(ReportAttachment)
        .where(ReportAttachment.report_id == report_id)
        .options(undefer(ReportAttachment.content))
    )
    return await db.scalar(query)


async def link_observable(
    db: AsyncSession,
    report_id: uuid.UUID,
    observable_id: uuid.UUID,
) -> tuple[Observable | None, bool]:
    if await db.get(Report, report_id) is None:
        return None, False
    observable = await db.get(Observable, observable_id)
    if observable is None:
        return None, False
    existing = await db.scalar(
        select(report_observables.c.report_id).where(
            report_observables.c.report_id == report_id,
            report_observables.c.observable_id == observable_id,
        )
    )
    if existing is not None:
        return observable, False
    await db.execute(
        insert(report_observables).values(
            report_id=report_id,
            observable_id=observable_id,
        )
    )
    await db.flush()
    return observable, True


async def unlink_observable(
    db: AsyncSession,
    report_id: uuid.UUID,
    observable_id: uuid.UUID,
) -> bool:
    if await db.get(Report, report_id) is None:
        return False
    existing = await db.scalar(
        select(report_observables.c.report_id).where(
            report_observables.c.report_id == report_id,
            report_observables.c.observable_id == observable_id,
        )
    )
    if existing is None:
        return False
    await db.execute(
        delete(report_observables).where(
            report_observables.c.report_id == report_id,
            report_observables.c.observable_id == observable_id,
        )
    )
    await recompute_effective_confidence(db, [observable_id])
    await db.flush()
    return True


async def list_reports_for_observable(
    db: AsyncSession,
    observable_id: uuid.UUID,
) -> list[Report] | None:
    if await db.get(Observable, observable_id) is None:
        return None
    query = (
        select(Report)
        .join(report_observables, report_observables.c.report_id == Report.id)
        .where(report_observables.c.observable_id == observable_id)
        .options(*_load_options())
        .order_by(Report.created_at.desc())
    )
    return list((await db.scalars(query)).unique().all())
