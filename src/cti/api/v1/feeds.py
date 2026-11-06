"""Feed CRUD, trigger, and run history endpoints."""

# ruff: noqa: B008 - FastAPI dependencies are intentionally declared in defaults.

from __future__ import annotations

import logging
import uuid  # noqa: TC003 - FastAPI resolves endpoint annotations at runtime.

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import (  # noqa: TC002 - FastAPI resolves this annotation.
    AsyncSession,
)

from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth
from cti.core.redis import invalidate_observable_caches
from cti.feeds.defaults import DEFAULT_FEEDS
from cti.models.tlp import Tlp
from cti.schemas.feed import FeedCreate, FeedResponse, FeedRunResponse, FeedUpdate
from cti.services import audit, feed_service
from cti.services.feed_auth import (
    AuthConfigValidationError,
    stored_auth_needs_repair,
    try_decrypt_stored_auth,
)
from cti.services.tlp import TlpDowngradeReasonRequiredError, hide_red_for

logger = logging.getLogger(__name__)

router = APIRouter()

# Preconfigured feeds that expect an API key (from defaults.py `requires_api_key`).
_AUTH_FEED_NAMES = {d["name"] for d in DEFAULT_FEEDS if d.get("requires_api_key")}
_SENSITIVE_CHANGE_FIELDS = frozenset({"auth_config", "tlp_change_reason"})


def _changed_fields(data: FeedCreate | FeedUpdate) -> list[str]:
    return sorted(data.model_fields_set - _SENSITIVE_CHANGE_FIELDS)


async def _record_failure(
    db: AsyncSession,
    *,
    actor: audit.Actor,
    action: str,
    status: int,
    reason: str,
    resource_id: object = None,
    resource_label: object = None,
    outcome: audit.AuditOutcome = audit.AuditOutcome.FAILED,
) -> None:
    await db.rollback()
    await audit.record_independent(
        actor=actor,
        action=action,
        resource_type="feed",
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=outcome,
        summary={"reason": reason, "status": status},
        strict=False,
    )


def _feed_auth_needs_repair(feed) -> bool:
    if feed.auth_config_encrypted is None:
        return False
    decrypted = try_decrypt_stored_auth(feed.auth_config_encrypted)
    if decrypted is None:
        logger.warning(
            "Feed auth could not be decrypted; marking auth_needs_repair",
            extra={"feed_id": str(feed.id)},
        )
        return True
    return stored_auth_needs_repair(decrypted, feed_url=feed.url)


def _feed_to_response(feed, observable_count: int = 0) -> FeedResponse:
    latest_run = None
    if feed.runs:
        r = feed.runs[0]
        latest_run = FeedRunResponse(
            id=r.id,
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            observables_ingested=r.observables_ingested,
            observables_new=r.observables_new,
            error_message=r.error_message,
        )

    return FeedResponse(
        id=feed.id,
        name=feed.name,
        description=feed.description,
        feed_type=feed.feed_type,
        url=feed.url,
        config=feed.config,
        schedule_cron=feed.schedule_cron,
        enabled=feed.enabled,
        is_preconfigured=feed.is_preconfigured,
        has_auth=feed.auth_config_encrypted is not None,
        auth_supported=feed.is_preconfigured and feed.name in _AUTH_FEED_NAMES,
        auth_needs_repair=_feed_auth_needs_repair(feed),
        default_confidence=feed.default_confidence,
        tlp=feed.tlp,
        last_run_at=feed.last_run_at,
        observable_count=observable_count,
        latest_run=latest_run,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


@router.get("", response_model=list[FeedResponse])
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[FeedResponse]:
    feeds = await feed_service.list_feeds(db)
    result = []
    for feed in feeds:
        count = await feed_service.get_observable_count_for_feed(db, feed.id)
        result.append(_feed_to_response(feed, observable_count=count))
    return result


@router.post("", response_model=FeedResponse, status_code=201)
async def create_feed(
    data: FeedCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(audit.audited_admin("feed.create", "feed")),
) -> FeedResponse:
    actor = audit.actor_from_auth(auth)
    try:
        feed = await feed_service.create_feed(db, data.model_dump())
    except AuthConfigValidationError as e:
        await _record_failure(
            db,
            actor=actor,
            action="feed.create",
            status=422,
            reason="invalid_configuration",
            resource_label=data.name,
        )
        raise HTTPException(status_code=422, detail=e.message) from None
    audit.record(
        db,
        actor=actor,
        action="feed.create",
        resource_type="feed",
        resource_id=feed.id,
        resource_label=feed.name,
        summary={"changed_fields": _changed_fields(data)},
    )
    await db.commit()

    # Sync scheduler if feed is enabled with a schedule
    if feed.enabled and feed.schedule_cron:
        from cti.services.scheduler import sync_feed_jobs

        await sync_feed_jobs(db)

    return _feed_to_response(feed)


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> FeedResponse:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    count = await feed_service.get_observable_count_for_feed(db, feed.id)
    return _feed_to_response(feed, observable_count=count)


@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: uuid.UUID,
    data: FeedUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("feed.update", "feed", resource_id_param="feed_id")
    ),
) -> FeedResponse:
    actor = audit.actor_from_auth(auth)
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        await _record_failure(
            db,
            actor=actor,
            action="feed.update",
            status=404,
            reason="not_found",
            resource_id=feed_id,
        )
        raise HTTPException(status_code=404, detail="Feed not found")
    label = feed.name
    tlp_before = feed.tlp
    if (
        hide_red_for(auth)
        and feed.tlp == Tlp.RED.value
        and "tlp" in data.model_fields_set
        and data.tlp is not Tlp.RED
    ):
        # Declassifying a RED feed would make its observables exportable.
        await _record_failure(
            db,
            actor=actor,
            action="feed.update",
            status=403,
            reason="interactive_admin_required",
            resource_id=feed_id,
            resource_label=label,
            outcome=audit.AuditOutcome.DENIED,
        )
        raise HTTPException(
            status_code=403,
            detail="Declassifying a TLP:RED feed requires an interactive admin session",
        )

    try:
        feed = await feed_service.update_feed(db, feed, data.model_dump(exclude_unset=True))
    except AuthConfigValidationError as e:
        await _record_failure(
            db,
            actor=actor,
            action="feed.update",
            status=422,
            reason="invalid_configuration",
            resource_id=feed_id,
            resource_label=label,
        )
        raise HTTPException(status_code=422, detail=e.message) from None
    except TlpDowngradeReasonRequiredError as e:
        await _record_failure(
            db,
            actor=actor,
            action="feed.update",
            status=422,
            reason="tlp_reason_required",
            resource_id=feed_id,
            resource_label=label,
        )
        raise HTTPException(status_code=422, detail=str(e)) from None
    summary: dict[str, object] = {"changed_fields": _changed_fields(data)}
    if "tlp" in data.model_fields_set:
        summary.update({"before": tlp_before, "after": feed.tlp})
    audit.record(
        db,
        actor=actor,
        action="feed.update",
        resource_type="feed",
        resource_id=feed.id,
        resource_label=feed.name,
        summary=summary,
    )
    await db.commit()
    await db.refresh(feed)
    if "tlp" in data.model_fields_set:
        # The feed marking feeds every contributed observable's effective marking.
        await invalidate_observable_caches()

    # Sync scheduler after feed update
    from cti.services.scheduler import sync_feed_jobs

    await sync_feed_jobs(db)

    count = await feed_service.get_observable_count_for_feed(db, feed.id)
    return _feed_to_response(feed, observable_count=count)


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("feed.delete", "feed", resource_id_param="feed_id")
    ),
) -> None:
    actor = audit.actor_from_auth(auth)
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        await _record_failure(
            db,
            actor=actor,
            action="feed.delete",
            status=404,
            reason="not_found",
            resource_id=feed_id,
        )
        raise HTTPException(status_code=404, detail="Feed not found")
    label = feed.name
    if hide_red_for(auth) and feed.tlp == Tlp.RED.value:
        # Removing the feed drops its RED marking from every contributed observable.
        await _record_failure(
            db,
            actor=actor,
            action="feed.delete",
            status=403,
            reason="interactive_admin_required",
            resource_id=feed_id,
            resource_label=label,
            outcome=audit.AuditOutcome.DENIED,
        )
        raise HTTPException(
            status_code=403,
            detail="Deleting a TLP:RED feed requires an interactive admin session",
        )

    try:
        deleted = await feed_service.delete_feed(db, feed)
    except feed_service.FeedInUseError as exc:
        used_by = (
            f"export profile(s): {', '.join(exc.profile_names)}"
            if exc.profile_names
            else "an export profile"
        )
        await _record_failure(
            db,
            actor=actor,
            action="feed.delete",
            status=409,
            reason="in_use",
            resource_id=feed_id,
            resource_label=label,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Feed is used by {used_by}. "
                "Update or delete those profiles before deleting the feed."
            ),
        ) from None
    if not deleted:
        await _record_failure(
            db,
            actor=actor,
            action="feed.delete",
            status=400,
            reason="preconfigured",
            resource_id=feed_id,
            resource_label=label,
        )
        raise HTTPException(
            status_code=400, detail="Cannot delete pre-configured feeds. Disable them instead."
        )
    audit.record(
        db,
        actor=actor,
        action="feed.delete",
        resource_type="feed",
        resource_id=feed_id,
        resource_label=label,
    )
    await db.commit()
    await invalidate_observable_caches()

    from cti.services.scheduler import sync_feed_jobs

    await sync_feed_jobs(db)


@router.post("/{feed_id}/trigger", response_model=FeedRunResponse)
async def trigger_feed(
    feed_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    auth: AuthSubject = Depends(
        audit.audited_admin("feed.trigger", "feed", resource_id_param="feed_id")
    ),
) -> FeedRunResponse:
    actor = audit.actor_from_auth(auth)
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        await _record_failure(
            db,
            actor=actor,
            action="feed.trigger",
            status=404,
            reason="not_found",
            resource_id=feed_id,
        )
        raise HTTPException(status_code=404, detail="Feed not found")
    if not feed.enabled:
        await _record_failure(
            db,
            actor=actor,
            action="feed.trigger",
            status=400,
            reason="disabled",
            resource_id=feed_id,
            resource_label=feed.name,
        )
        raise HTTPException(status_code=400, detail="Feed is not enabled")

    run = await feed_service.create_feed_run(db, feed.id)
    audit.record(
        db,
        actor=actor,
        action="feed.trigger",
        resource_type="feed",
        resource_id=feed.id,
        resource_label=feed.name,
        summary={"run_id": str(run.id)},
    )
    await db.commit()

    # Run in background so API responds immediately
    async def _bg_run() -> None:
        from cti.core.database import async_session_factory
        from cti.feeds.runner import run_feed

        async with async_session_factory() as bg_db:
            await run_feed(feed_id, bg_db, run_id=run.id)

    background_tasks.add_task(_bg_run)

    return FeedRunResponse(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        observables_ingested=run.observables_ingested,
        observables_new=run.observables_new,
        error_message=run.error_message,
    )


@router.get("/{feed_id}/runs", response_model=list[FeedRunResponse])
async def get_feed_runs(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[FeedRunResponse]:
    feed = await feed_service.get_feed(db, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    runs = await feed_service.get_feed_runs(db, feed.id)
    return [
        FeedRunResponse(
            id=r.id,
            started_at=r.started_at,
            completed_at=r.completed_at,
            status=r.status,
            observables_ingested=r.observables_ingested,
            observables_new=r.observables_new,
            error_message=r.error_message,
        )
        for r in runs
    ]
