"""Flat tags for observables and reports (#15)."""
# ruff: noqa: B008, TC002, TC003

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.redis import invalidate_observable_caches
from cti.schemas.tag import TagCreate, TagResponse, TagWithCounts
from cti.services import tag_service

router = APIRouter()


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
    _auth: AuthSubject = Depends(require_admin),
) -> TagResponse:
    """Create a tag; an existing (normalized) name returns that tag with 200."""
    try:
        name = tag_service.normalize_tag(data.name)
    except tag_service.TagValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    tag, created = await tag_service.get_or_create_tag(db, name)
    await db.commit()
    response.status_code = 201 if created else 200
    return TagResponse(id=tag.id, name=tag.name)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> Response:
    """Delete a tag and all its assignments; 409 if an export profile uses it."""
    tag = await tag_service.get_tag(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    try:
        await tag_service.delete_tag(db, tag)
    except tag_service.TagInUseError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Tag is used by export profiles: "
                f"{', '.join(exc.profile_names) or 'unknown'}. "
                "Remove it from those profiles first."
            ),
        ) from None
    await db.commit()
    await invalidate_observable_caches()
    return Response(status_code=204)
