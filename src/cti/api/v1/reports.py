"""Reports library endpoints."""
# ruff: noqa: B008, TC001, TC002, TC003

from __future__ import annotations

import uuid
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.api.v1.filters import parse_tag_names, parse_tlp_tokens
from cti.api.v1.tlp_guard import ensure_observable_visible, ensure_report_visible
from cti.core.config import get_settings
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.redis import invalidate_observable_caches
from cti.models.report import Report, ReportOrigin
from cti.models.report import ReportAttachment as ReportAttachmentModel
from cti.models.tlp import Tlp
from cti.models.user import User
from cti.schemas.observable import TagsUpdate
from cti.schemas.report import (
    ExtractionPreview,
    ImportRequest,
    ImportResult,
    LinkedObservable,
    ReportCreate,
    ReportDetail,
    ReportFilters,
    ReportListResponse,
    ReportObservableLink,
    ReportSummary,
    ReportUpdate,
)
from cti.schemas.report import (
    ReportAttachment as ReportAttachmentSchema,
)
from cti.services import audit, report_import_service, report_service, tag_service
from cti.services.tlp import hide_red_for, marking_key, red_observable_ids

router = APIRouter()


# ── Audit helpers ──────────────────────────────────────────────────────────

_FAILURE_REASONS = {
    404: "not_found",
    413: "too_large",
    415: "unsupported_type",
    422: "invalid",
}


async def _record_failure(
    db: AsyncSession,
    actor: audit.Actor,
    action: str,
    report_id: uuid.UUID,
    exc: HTTPException,
    label: str | None = None,
    *,
    extra: dict[str, object] | None = None,
) -> None:
    """Record a failed report action. Roll back first: the request is doomed.

    ``label`` is only passed once the report is known to be visible to the
    caller, so a RED report hidden from an API key leaves no title behind.
    """
    await audit.rollback_for_independent_audit(db, actor=actor)
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type="report",
        resource_id=report_id,
        resource_label=label,
        outcome=audit.AuditOutcome.FAILED,
        summary={
            **(extra or {}),
            "reason": _FAILURE_REASONS.get(exc.status_code, "error"),
            "status": exc.status_code,
        },
        strict=False,
    )


async def _report_title(db: AsyncSession, report_id: uuid.UUID) -> str | None:
    return await db.scalar(select(Report.title).where(Report.id == report_id))


async def _attachment_metadata(
    db: AsyncSession, report_id: uuid.UUID
) -> ReportAttachmentModel | None:
    """The attachment row without its (deferred) bytes."""
    return await db.scalar(
        select(ReportAttachmentModel).where(ReportAttachmentModel.report_id == report_id)
    )


def _attachment_summary(attachment: ReportAttachmentModel) -> dict[str, object]:
    # "media_type", not "content_type": the sanitizer drops keys containing "content".
    return {
        "filename": attachment.original_filename,
        "media_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
    }


def report_to_summary(report: Report) -> ReportSummary:
    return ReportSummary(
        id=report.id,
        title=report.title,
        origin=report.origin,
        source_name=report.source_name,
        published_at=report.published_at,
        summary=report.summary,
        is_ai_generated=report.is_ai_generated,
        ai_provider=report.ai_provider,
        ai_model=report.ai_model,
        has_attachment=report.attachment is not None,
        tlp=report.tlp,
        tags=sorted(tag.name for tag in report.tags),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def report_to_detail(
    report: Report, hidden_observable_ids: frozenset[uuid.UUID] | set[uuid.UUID] = frozenset()
) -> ReportDetail:
    summary = report_to_summary(report).model_dump()
    return ReportDetail(
        **summary,
        source_url=report.source_url,
        content=report.content,
        content_format=report.content_format,
        ai_generated_at=report.ai_generated_at,
        created_by=report.created_by.username if report.created_by is not None else None,
        attachment=(
            ReportAttachmentSchema.model_validate(report.attachment)
            if report.attachment is not None
            else None
        ),
        observables=[
            LinkedObservable.model_validate(item)
            for item in report.observables
            if item.id not in hidden_observable_ids
        ],
    )


async def _mutation_detail(
    db: AsyncSession, report: Report, auth: object
) -> ReportDetail | Response:
    """After an API key's change leaves the report RED, do not echo it back: 204."""
    if hide_red_for(auth) and report.tlp == Tlp.RED.value:
        return Response(status_code=204)
    return await report_detail_for(db, report, auth)


async def report_detail_for(db: AsyncSession, report: Report, auth: object) -> ReportDetail:
    """ReportDetail; API-key callers do not see linked RED observables."""
    hidden: set[uuid.UUID] = set()
    if hide_red_for(auth) and report.observables:
        hidden = await red_observable_ids(db, (o.id for o in report.observables))
    return report_to_detail(report, hidden)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
    q: str | None = None,
    origin: ReportOrigin | None = None,
    source_name: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    ai_generated: bool | None = None,
    tag: list[str] | None = Query(default=None, description="Match ANY listed tag"),
    tlp: list[str] | None = Query(default=None, description="Marking or 'unspecified'"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
) -> ReportListResponse:
    filters = ReportFilters(
        tags=parse_tag_names(tag),
        tlp=parse_tlp_tokens(tlp),
        exclude_red=hide_red_for(auth),
        q=q,
        origin=origin,
        source_name=source_name,
        published_from=published_from,
        published_to=published_to,
        ai_generated=ai_generated,
        page=page,
        size=size,
    )
    reports, total = await report_service.list_reports(db, filters)
    pages = (total + size - 1) // size if total else 0
    return ReportListResponse(
        items=[report_to_summary(report) for report in reports],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/sources", response_model=list[str])
async def list_report_sources(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[str]:
    return await report_service.list_sources(db)


@router.post("", response_model=ReportDetail, status_code=201)
async def create_report(
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(audit.audited_admin("report.create", "report")),
) -> ReportDetail | Response:
    actor = audit.actor_from_auth(auth)
    created_by_id = auth.id if isinstance(auth, User) else None
    report = await report_service.create_report(db, data, created_by_id=created_by_id)
    audit.record(
        db,
        actor=actor,
        action="report.create",
        resource_type="report",
        resource_id=report.id,
        resource_label=report.title,
        summary={"tlp": report.tlp},
    )
    await db.commit()
    return await _mutation_detail(db, report, auth)


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
) -> ReportDetail:
    await ensure_report_visible(db, auth, report_id)
    report = await report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return await report_detail_for(db, report, auth)


# Columns compared for ``report.update``'s ``changed_fields`` (names only).
_UPDATABLE_FIELDS = frozenset(ReportUpdate.model_fields) - {"tlp_change_reason"}


@router.patch("/{report_id}", response_model=ReportDetail)
async def update_report(
    report_id: uuid.UUID,
    data: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.update", "report", resource_id_param="report_id")
    ),
) -> ReportDetail | Response:
    actor = audit.actor_from_auth(auth)
    label: str | None = None
    try:
        await ensure_report_visible(db, auth, report_id)
        current = await report_service.get_report(db, report_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Report not found")
        label = current.title
        fields = sorted(_UPDATABLE_FIELDS & data.model_fields_set)
        # Scalars only: update_report mutates this same identity-mapped object.
        before = {field: getattr(current, field) for field in fields}
        try:
            report = await report_service.update_report(db, report_id, data)
        except report_service.ReportValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.update", report_id, exc, label)
        raise
    changed = [field for field in fields if before[field] != getattr(report, field)]
    summary: dict[str, object] = {"changed_fields": changed}
    if "tlp" in changed:
        summary["tlp"] = {"before": before["tlp"], "after": report.tlp}
    audit.record(
        db,
        actor=actor,
        action="report.update",
        resource_type="report",
        resource_id=report.id,
        resource_label=report.title,
        summary=summary,
    )
    await db.commit()
    if "tlp" in data.model_fields_set:
        # A report marking feeds its linked observables' effective markings.
        await invalidate_observable_caches()
    return await _mutation_detail(db, report, auth)


@router.put("/{report_id}/tags", response_model=ReportDetail)
async def set_report_tags(
    report_id: uuid.UUID,
    data: TagsUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.tags_update", "report", resource_id_param="report_id")
    ),
) -> ReportDetail | Response:
    """Replace the report's tag set (names are normalized; new ones created)."""
    actor = audit.actor_from_auth(auth)
    label: str | None = None
    try:
        await ensure_report_visible(db, auth, report_id)
        current = await report_service.get_report(db, report_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Report not found")
        label = current.title
        before = {tag.name for tag in current.tags}
        try:
            await tag_service.set_report_tags(db, report_id, data.tags)
        except tag_service.TagValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    except HTTPException as exc:
        await _record_failure(db, actor, "report.tags_update", report_id, exc, label)
        raise
    report = await report_service.get_report(db, report_id, refresh=True)
    assert report is not None
    after = {tag.name for tag in report.tags}
    audit.record(
        db,
        actor=actor,
        action="report.tags_update",
        resource_type="report",
        resource_id=report_id,
        resource_label=report.title,
        summary={"added": sorted(after - before), "removed": sorted(before - after)},
    )
    await db.commit()
    return await _mutation_detail(db, report, auth)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.delete", "report", resource_id_param="report_id")
    ),
) -> Response:
    actor = audit.actor_from_auth(auth)
    try:
        await ensure_report_visible(db, auth, report_id)
        # Snapshot before deletion so the history keeps a readable label.
        label = await _report_title(db, report_id)
        if not await report_service.delete_report(db, report_id):
            raise HTTPException(status_code=404, detail="Report not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.delete", report_id, exc)
        raise
    audit.record(
        db,
        actor=actor,
        action="report.delete",
        resource_type="report",
        resource_id=report_id,
        resource_label=label,
    )
    await db.commit()
    await invalidate_observable_caches()
    return Response(status_code=204)


@router.put("/{report_id}/attachment", response_model=ReportAttachmentSchema)
async def upload_report_attachment(
    report_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.attachment_upload", "report", resource_id_param="report_id")
    ),
) -> ReportAttachmentSchema:
    actor = audit.actor_from_auth(auth)
    label: str | None = None
    try:
        await ensure_report_visible(db, auth, report_id)
        label = await _report_title(db, report_id)
        if label is None:
            raise HTTPException(status_code=404, detail="Report not found")
        try:
            filename, content_type, content = await report_service.read_and_validate_upload(
                file,
                get_settings().REPORT_MAX_UPLOAD_BYTES,
            )
        except report_service.UploadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from None
        except report_service.EmptyUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except report_service.UnsupportedUploadError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from None
    except HTTPException as exc:
        await _record_failure(db, actor, "report.attachment_upload", report_id, exc, label)
        raise

    attachment = await report_service.replace_attachment(
        db,
        report_id,
        original_filename=filename,
        content_type=content_type,
        content=content,
    )
    assert attachment is not None
    audit.record(
        db,
        actor=actor,
        action="report.attachment_upload",
        resource_type="report",
        resource_id=report_id,
        resource_label=label,
        summary=_attachment_summary(attachment),
    )
    await db.commit()
    return ReportAttachmentSchema.model_validate(attachment)


@router.delete("/{report_id}/attachment", status_code=204)
async def delete_report_attachment(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.attachment_delete", "report", resource_id_param="report_id")
    ),
) -> Response:
    actor = audit.actor_from_auth(auth)
    label: str | None = None
    try:
        await ensure_report_visible(db, auth, report_id)
        label = await _report_title(db, report_id)
        # Metadata only: ``content`` is deferred and never loaded here.
        attachment = await _attachment_metadata(db, report_id)
        summary = _attachment_summary(attachment) if attachment is not None else {}
        if not await report_service.delete_attachment(db, report_id):
            raise HTTPException(status_code=404, detail="Report attachment not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.attachment_delete", report_id, exc, label)
        raise
    audit.record(
        db,
        actor=actor,
        action="report.attachment_delete",
        resource_type="report",
        resource_id=report_id,
        resource_label=label,
        summary=summary,
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/{report_id}/attachment")
async def download_report_attachment(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(get_current_auth),
) -> Response:
    actor = audit.actor_from_auth(auth)
    try:
        await ensure_report_visible(db, auth, report_id, "Report attachment not found")
        # Metadata first; the bytes are read only after ``initiated`` is durable.
        metadata = await _attachment_metadata(db, report_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Report attachment not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.attachment_download", report_id, exc)
        raise
    # The attachment inherits the report's marking. A RED report is invisible
    # to API keys (404 above); interactive user sessions may still download it.
    tlp_header = marking_key(await report_service.get_report_tlp(db, report_id))
    summary = {**_attachment_summary(metadata), "tlp": tlp_header}
    disclosure = await audit.begin_disclosure(
        actor=actor,
        action="report.attachment_download",
        resource_type="report",
        resource_id=report_id,
        resource_label=await _report_title(db, report_id),
        summary=summary,
    )
    attachment = await report_service.get_attachment_for_download(db, report_id)
    if attachment is None:  # Deleted between the metadata read and now.
        await disclosure.record_outcome(
            audit.AuditOutcome.FAILED, {"reason": "not_found", "status": 404}
        )
        raise HTTPException(status_code=404, detail="Report attachment not found")
    encoded_filename = quote(attachment.original_filename, safe="")
    return audit.AuditedDownload(
        attachment.content,
        disclosure=disclosure,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "private, no-store",
            "X-TLP-Marking": tlp_header,
        },
    )


@router.post("/{report_id}/observables", response_model=LinkedObservable, status_code=201)
async def link_report_observable(
    report_id: uuid.UUID,
    data: ReportObservableLink,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.observable_link", "report", resource_id_param="report_id")
    ),
) -> LinkedObservable:
    actor = audit.actor_from_auth(auth)
    summary = {"observable_id": data.observable_id}
    try:
        await ensure_report_visible(db, auth, report_id, "Report or observable not found")
        await ensure_observable_visible(
            db, auth, data.observable_id, "Report or observable not found"
        )
        observable, created = await report_service.link_observable(
            db,
            report_id,
            data.observable_id,
        )
        if observable is None:
            raise HTTPException(status_code=404, detail="Report or observable not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.observable_link", report_id, exc, extra=summary)
        raise
    audit.record(
        db,
        actor=actor,
        action="report.observable_link",
        resource_type="report",
        resource_id=report_id,
        resource_label=await _report_title(db, report_id),
        summary={**summary, "created": created},
    )
    await db.commit()
    response.status_code = 201 if created else 200
    return LinkedObservable.model_validate(observable)


@router.delete("/{report_id}/observables/{observable_id}", status_code=204)
async def unlink_report_observable(
    report_id: uuid.UUID,
    observable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.observable_unlink", "report", resource_id_param="report_id")
    ),
) -> Response:
    actor = audit.actor_from_auth(auth)
    summary = {"observable_id": observable_id}
    try:
        await ensure_report_visible(db, auth, report_id, "Report-observable link not found")
        await ensure_observable_visible(db, auth, observable_id, "Report-observable link not found")
        if not await report_service.unlink_observable(db, report_id, observable_id):
            raise HTTPException(status_code=404, detail="Report-observable link not found")
    except HTTPException as exc:
        await _record_failure(db, actor, "report.observable_unlink", report_id, exc, extra=summary)
        raise
    audit.record(
        db,
        actor=actor,
        action="report.observable_unlink",
        resource_type="report",
        resource_id=report_id,
        resource_label=await _report_title(db, report_id),
        summary=summary,
    )
    await db.commit()
    await invalidate_observable_caches()
    return Response(status_code=204)


@router.post("/{report_id}/extract", response_model=ExtractionPreview)
async def extract_report_indicators(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(require_admin),
) -> ExtractionPreview:
    """Preview IOC candidates in the report. Read-only: performs no writes."""
    await ensure_report_visible(db, auth, report_id)
    report = await report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    # API keys: RED matches are previewed exactly as values that do not exist.
    return await report_import_service.build_preview(db, report, hide_red=hide_red_for(auth))


@router.post("/{report_id}/import", response_model=ImportResult)
async def import_report_indicators(
    report_id: uuid.UUID,
    data: ImportRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("report.import", "report", resource_id_param="report_id")
    ),
) -> ImportResult:
    """Import analyst-selected candidates in one transaction."""
    actor = audit.actor_from_auth(auth)
    label: str | None = None
    try:
        await ensure_report_visible(db, auth, report_id)
        report = await report_service.get_report(db, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        label = report.title
        try:
            result = await report_import_service.import_candidates(
                db,
                report,
                confidence=data.confidence,
                items=data.items,
                imported_by_id=auth.id if isinstance(auth, User) else None,
                hide_red=hide_red_for(auth),
            )
        except report_import_service.NotACandidateError as exc:
            raise HTTPException(status_code=422, detail=exc.detail) from None
    except HTTPException as exc:
        await _record_failure(
            db, actor, "report.import", report_id, exc, label, extra={"requested": len(data.items)}
        )
        raise
    # Counts and observable ids only: never the indicator values.
    audit.record(
        db,
        actor=actor,
        action="report.import",
        resource_type="report",
        resource_id=report_id,
        resource_label=label,
        summary={
            "requested": len(data.items),
            "created": result.created,
            "attributed_existing": result.attributed_existing,
            "already_attributed": result.already_attributed,
            "skipped": len(result.skipped),
            "observable_ids": [item.id for item in result.observables],
        },
    )
    await db.commit()
    await invalidate_observable_caches()
    return result
