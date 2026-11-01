"""Allowlist policy endpoints: reversible export suppression."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.schemas.allowlist import AllowlistEntryCreate, AllowlistEntryResponse
from cti.services import allowlist_service

router = APIRouter()


@router.get("", response_model=list[AllowlistEntryResponse])
async def list_allowlist(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[AllowlistEntryResponse]:
    entries = await allowlist_service.list_entries(db)
    return [AllowlistEntryResponse.model_validate(e) for e in entries]


@router.post("", response_model=AllowlistEntryResponse, status_code=201)
async def create_allowlist_entry(
    data: AllowlistEntryCreate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> AllowlistEntryResponse:
    try:
        entry = await allowlist_service.create_entry(
            db,
            kind=data.kind,
            value=data.value,
            observable_type=data.observable_type,
            reason=data.reason,
        )
    except allowlist_service.AllowlistValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except allowlist_service.DuplicateAllowlistEntryError:
        raise HTTPException(
            status_code=409, detail="An identical allowlist entry already exists"
        ) from None
    await db.commit()
    return AllowlistEntryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_allowlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    deleted = await allowlist_service.delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Allowlist entry not found")
    await db.commit()
