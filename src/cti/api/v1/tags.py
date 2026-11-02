"""Flat tags for observables and reports (#15)."""
# ruff: noqa: B008, TC002, TC003

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.core.redis import invalidate_observable_caches
from cti.schemas.tag import TagCreate, TagResponse, TagWithCounts
from cti.services import audit, tag_service

router = APIRouter()


async def _rollback_for_audit(db: AsyncSession) -> None:
    """Roll back before an independent write, preserving clean loaded identities."""
    loaded = [
        (
            obj,
            {
                attr.key: state.dict[attr.key]
                for attr in state.mapper.column_attrs
                if attr.key in state.dict
            },
        )
        for obj in list(db.sync_session.identity_map.values())
        if not (state := inspect(obj)).modified
    ]
    await db.rollback()
    for obj, values in loaded:
        if inspect(obj).persistent:
            for key, value in values.items():
                set_committed_value(obj, key, value)


async def _record_failure(
    db: AsyncSession,
    *,
    actor: audit.Actor,
    action: str,
    status: int,
    reason: str,
    resource_id: object = None,
    resource_label: object = None,
) -> None:
    await _rollback_for_audit(db)
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type="tag",
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=audit.AuditOutcome.FAILED,
        summary={"reason": reason, "status": status},
        strict=False,
    )


@router.get("", response_model=list[TagWithCounts])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
    q: str | None = None,
) -> list[TagWithCounts]:
    """Every tag, sorted by name, optionally filtered by name prefix."""
    rows = await tag_service.list_tags(db, prefix=q)
    return [
        TagWithCounts(id=tag.id, name=tag.name, observable_count=obs, report_count=rep)
        for tag, obs, rep in rows
    ]


@router.post("", response_model=TagResponse, status_code=201)
async def create_tag(
    data: TagCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(audit.audited_admin("tag.create", "tag")),
) -> TagResponse:
    """Create a tag; an existing (normalized) name returns that tag with 200."""
    actor = audit.actor_from_auth(auth)
    try:
        name = tag_service.normalize_tag(data.name)
    except tag_service.TagValidationError as exc:
        await _record_failure(
            db, actor=actor, action="tag.create", status=422, reason="invalid_name"
        )
        raise HTTPException(status_code=422, detail=str(exc)) from None
    tag, created = await tag_service.get_or_create_tag(db, name)
    audit.record(
        db,
        actor=actor,
        action="tag.create",
        resource_type="tag",
        resource_id=tag.id,
        resource_label=tag.name,
        summary={"created": created},
    )
    await db.commit()
    response.status_code = 201 if created else 200
    return TagResponse(id=tag.id, name=tag.name)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("tag.delete", "tag", resource_id_param="tag_id")
    ),
) -> Response:
    """Delete a tag and all its assignments; 409 if an export profile uses it."""
    actor = audit.actor_from_auth(auth)
    tag = await tag_service.get_tag(db, tag_id)
    if tag is None:
        await _record_failure(
            db,
            actor=actor,
            action="tag.delete",
            status=404,
            reason="not_found",
            resource_id=tag_id,
        )
        raise HTTPException(status_code=404, detail="Tag not found")
    try:
        await tag_service.delete_tag(db, tag)
    except tag_service.TagInUseError as exc:
        await _record_failure(
            db,
            actor=actor,
            action="tag.delete",
            status=409,
            reason="in_use",
            resource_id=tag_id,
            resource_label=tag.name,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Tag is used by export profiles: "
                f"{', '.join(exc.profile_names) or 'unknown'}. "
                "Remove it from those profiles first."
            ),
        ) from None
    audit.record(
        db,
        actor=actor,
        action="tag.delete",
        resource_type="tag",
        resource_id=tag_id,
        resource_label=tag.name,
    )
    await db.commit()
    await invalidate_observable_caches()
    return Response(status_code=204)
