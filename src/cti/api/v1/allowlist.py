"""Allowlist policy endpoints: reversible export suppression."""
# ruff: noqa: B008, TC002, TC003

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.models.allowlist import AllowlistEntry
from cti.schemas.allowlist import AllowlistEntryCreate, AllowlistEntryResponse
from cti.services import allowlist_service, audit

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
        resource_type="allowlist_entry",
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=audit.AuditOutcome.FAILED,
        summary={"reason": reason, "status": status},
        strict=False,
    )


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
    auth: AuthSubject = Depends(audit.audited_admin("allowlist.create", "allowlist_entry")),
) -> AllowlistEntryResponse:
    actor = audit.actor_from_auth(auth)
    try:
        entry = await allowlist_service.create_entry(
            db,
            kind=data.kind,
            value=data.value,
            observable_type=data.observable_type,
            reason=data.reason,
        )
    except allowlist_service.AllowlistValidationError as exc:
        await _record_failure(
            db,
            actor=actor,
            action="allowlist.create",
            status=422,
            reason="invalid_entry",
            resource_label=data.value,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except allowlist_service.DuplicateAllowlistEntryError:
        await _record_failure(
            db,
            actor=actor,
            action="allowlist.create",
            status=409,
            reason="duplicate",
            resource_label=data.value,
        )
        raise HTTPException(
            status_code=409, detail="An identical allowlist entry already exists"
        ) from None
    audit.record(
        db,
        actor=actor,
        action="allowlist.create",
        resource_type="allowlist_entry",
        resource_id=entry.id,
        resource_label=entry.value,
        summary={
            "kind": entry.kind.value,
            "observable_type": entry.observable_type.value,
            "reason_length": len(entry.reason),
        },
    )
    await db.commit()
    return AllowlistEntryResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_allowlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin(
            "allowlist.delete", "allowlist_entry", resource_id_param="entry_id"
        )
    ),
) -> None:
    actor = audit.actor_from_auth(auth)
    entry = await db.get(AllowlistEntry, entry_id)
    if entry is None:
        await _record_failure(
            db,
            actor=actor,
            action="allowlist.delete",
            status=404,
            reason="not_found",
            resource_id=entry_id,
        )
        raise HTTPException(status_code=404, detail="Allowlist entry not found")
    deleted = await allowlist_service.delete_entry(db, entry_id)
    if not deleted:
        await _record_failure(
            db,
            actor=actor,
            action="allowlist.delete",
            status=404,
            reason="not_found",
            resource_id=entry_id,
        )
        raise HTTPException(status_code=404, detail="Allowlist entry not found")
    audit.record(
        db,
        actor=actor,
        action="allowlist.delete",
        resource_type="allowlist_entry",
        resource_id=entry_id,
        resource_label=entry.value,
        summary={"kind": entry.kind.value, "observable_type": entry.observable_type.value},
    )
    await db.commit()
