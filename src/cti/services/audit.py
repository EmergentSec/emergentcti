"""Audit history: attributable, append-only records of sensitive actions (issue #16).

Binding contract: ``docs/superpowers/specs/2026-11-02-audit-history.md``.

There are two ways to write an event, and the choice is about transactions:

* :func:`record` adds the event to the caller's session. Use it for a
  **successful mutation**, before the route's ``await db.commit()``. The event
  commits with the change or not at all; if the audit insert fails, the commit
  fails and the mutation rolls back.
* :func:`record_independent` writes in its own session and commits at once. Use
  it for **failed/denied attempts** (the request transaction is about to roll
  back) and for **disclosures** (the event must exist before content leaves).

Usage
-----

Successful mutation, in the request transaction::

    actor = audit.actor_from_auth(auth)
    entry = await allowlist_service.create_entry(db, ...)
    audit.record(db, actor=actor, action="allowlist.create",
                 resource_type="allowlist_entry", resource_id=entry.id,
                 resource_label=entry.value)
    await db.commit()

Failed or denied attempt (request transaction is doomed). Build the actor
first, roll back, then record; roll back first because PostgreSQL rejects
statements in an aborted transaction and SQLite (tests) allows a single writer::

    actor = audit.actor_from_auth(auth)
    try:
        ...
    except DuplicateError:
        await db.rollback()
        await audit.record_independent(
            actor=actor, action="allowlist.create", resource_type="allowlist_entry",
            outcome=audit.AuditOutcome.FAILED,
            summary={"reason": "duplicate", "status": 409}, strict=False)
        raise HTTPException(409, ...) from None

Admin-only mutation whose non-admin attempts should be recorded as ``denied``::

    @router.delete("/{entry_id}")
    async def delete_entry(
        entry_id: uuid.UUID,
        auth: AuthSubject = Depends(
            audit.audited_admin("allowlist.delete", "allowlist_entry",
                                resource_id_param="entry_id")),
    ): ...

Disclosure (a download). ``begin_disclosure`` writes ``initiated`` strictly and
raises ``HTTPException(503, "Audit log unavailable")`` if it cannot; nothing has
been sent at that point. ``AuditedDownload`` then writes ``completed`` or
``interrupted`` once the body has been handed to the server (or not)::

    disclosure = await audit.begin_disclosure(
        actor=audit.actor_from_auth(auth), action="export.download",
        resource_type="export", resource_id=str(profile.id),
        resource_label=profile.name, summary={"format": "text", "count": n})
    return audit.AuditedDownload(body, disclosure=disclosure,
                                 media_type="text/plain", headers={...})

Outbound AI request: ``initiated`` (strict) before calling the provider, then
the outcome (never the prompt, response text, or provider error body)::

    meta = {"operation": "check", "provider": provider, "model": model}
    disclosure = await audit.begin_disclosure(
        actor=audit.actor_from_auth(auth), action="ai.request",
        resource_type="ai_provider", resource_id=provider, summary=meta)
    try:
        result = await adapter.check(...)
    except ProviderError as exc:
        await disclosure.record_outcome(
            audit.AuditOutcome.FAILED, {**meta, "error_code": exc.code})
        raise
    await disclosure.record_outcome(audit.AuditOutcome.SUCCEEDED, meta)

Every ``action`` must appear in :data:`ACTION_CATALOG` with its matching
``resource_type``; anything else raises ``ValueError`` (a programming error,
raised even by non-strict writes). Summaries always pass through
:func:`sanitize_summary`, but callers should still pass an explicit, minimal
dict. Log lines never include summary contents or exception messages (SQL
errors embed bound parameters); only the exception class name is logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import anyio
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, func, inspect, select
from starlette.responses import Response

from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.models.api_key import ApiKey
from cti.models.audit import ActorType, AuditEvent, AuditOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from starlette.types import Message, Receive, Scope, Send

__all__ = [
    "ACTION_CATALOG",
    "AUDIT_RETENTION_BATCH_SIZE",
    "Actor",
    "ActorType",
    "AuditOutcome",
    "AuditRetentionError",
    "AuditWriteError",
    "AuditedDownload",
    "Disclosure",
    "actor_from_auth",
    "audited_admin",
    "begin_disclosure",
    "list_events",
    "purge_expired_events",
    "record",
    "record_independent",
    "sanitize_summary",
    "system_actor",
]

logger = logging.getLogger(__name__)

# ── Action catalog ─────────────────────────────────────────────────────────

#: Every auditable action mapped to its ``resource_type``. The single source of
#: truth: writers are validated against it and ``GET /audit/meta`` exposes it.
ACTION_CATALOG: Mapping[str, str] = MappingProxyType(
    {
        "allowlist.create": "allowlist_entry",
        "allowlist.delete": "allowlist_entry",
        "export_profile.create": "export_profile",
        "export_profile.update": "export_profile",
        "export_profile.delete": "export_profile",
        "export.download": "export",
        "report.create": "report",
        "report.update": "report",
        "report.delete": "report",
        "report.tags_update": "report",
        "report.attachment_upload": "report",
        "report.attachment_delete": "report",
        "report.attachment_download": "report",
        "report.observable_link": "report",
        "report.observable_unlink": "report",
        "report.import": "report",
        "observable.tlp_override_set": "observable",
        "observable.tlp_override_clear": "observable",
        "observable.tags_update": "observable",
        "tag.create": "tag",
        "tag.delete": "tag",
        "feed.create": "feed",
        "feed.update": "feed",
        "feed.delete": "feed",
        "feed.trigger": "feed",
        "api_key.create": "api_key",
        "api_key.revoke": "api_key",
        "user.create": "user",
        "user.update": "user",
        "user.delete": "user",
        "user.password_change": "user",
        "ai_provider.key_save": "ai_provider",
        "ai_provider.delete": "ai_provider",
        "ai_default.set": "ai_default",
        "ai_default.clear": "ai_default",
        "ai_role.set": "ai_role",
        "ai_role.clear": "ai_role",
        "ai.request": "ai_provider",
        "ai_usage_policy.update": "ai_usage_policy",
        "ai_pricing.update": "ai_pricing",
        "ai_pricing.delete": "ai_pricing",
        "threat_intel.fetch": "threat_intel",
        "threat_intel.generate_report": "threat_intel",
        "retention.observables_cleanup": "retention",
        "audit.retention_cleanup": "audit",
    }
)

AUDIT_RETENTION_BATCH_SIZE = 5000
AUDIT_RETENTION_MIN_DAYS = 30
AUDIT_RETENTION_MAX_DAYS = 3650


class AuditWriteError(Exception):
    """A strict audit write failed; the guarded action must not proceed."""


class AuditRetentionError(Exception):
    """Audit retention failed part-way. ``deleted`` rows were already committed."""

    def __init__(self, deleted: int) -> None:
        super().__init__(f"audit retention failed after {deleted} deletions")
        self.deleted = deleted


# ── Actors ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Actor:
    """Who did it. ``id`` is a user UUID, an API-key *record* UUID, or a job id."""

    type: ActorType
    id: str | None
    label: str | None


def _loaded_attr(obj: object, name: str) -> Any:
    """Read an ORM attribute without triggering a lazy load (unsafe under async)."""
    state = inspect(obj, raiseerr=False)
    if state is None:
        return getattr(obj, name, None)
    value = state.dict.get(name)
    if value is None and name == "id" and state.identity:
        value = state.identity[0]
    return value


def actor_from_auth(auth: AuthSubject) -> Actor:
    """Actor for an authenticated request: user -> username, API key -> key record.

    Never returns the raw API key; the key is identified by its record id and
    name. Safe to call on an expired instance (after a rollback), but building
    the actor before rolling back keeps the label.
    """
    if isinstance(auth, ApiKey):
        key_id = _loaded_attr(auth, "id")
        return Actor(
            ActorType.API_KEY,
            str(key_id) if key_id is not None else None,
            _loaded_attr(auth, "name"),
        )
    user_id = _loaded_attr(auth, "id")
    return Actor(
        ActorType.USER,
        str(user_id) if user_id is not None else None,
        _loaded_attr(auth, "username"),
    )


def system_actor(job_id: str, label: str) -> Actor:
    """Actor for a scheduled job, e.g. ``system_actor("system:audit_retention", ...)``."""
    return Actor(ActorType.SYSTEM, job_id, label)


# ── Sanitization ───────────────────────────────────────────────────────────

_DENIED_KEY_PARTS = (
    "key",
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "auth_header",
    "cookie",
    "credential",
    "prompt",
    "response",
    "content",
    "body",
    "headers",
    "raw",
)
_ALLOWED_EXACT_KEYS = frozenset({"api_key_id"})
MAX_SUMMARY_STRING = 256
MAX_SUMMARY_LIST = 50
MAX_SUMMARY_DEPTH = 3
MAX_SUMMARY_BYTES = 4096
_MAX_FALLBACK_FIELD_NAME = 64
_DROP = object()


def _key_allowed(key: str) -> bool:
    if key in _ALLOWED_EXACT_KEYS:
        return True
    lowered = key.lower()
    return not any(part in lowered for part in _DENIED_KEY_PARTS)


def _clip_list(items: list[Any], level: int) -> list[Any]:
    head = (_clean(item, level) for item in items[:MAX_SUMMARY_LIST])
    cleaned = [c for c in head if c is not _DROP]
    if len(items) > MAX_SUMMARY_LIST:
        cleaned.append(f"…+{len(items) - MAX_SUMMARY_LIST} more")
    return cleaned


def _clean(value: Any, level: int) -> Any:
    """Clean a value held by a container at nesting ``level`` (root mapping = 1)."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Enum):
        return _clean(value.value, level)
    if isinstance(value, str):
        return str(value)[:MAX_SUMMARY_STRING]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping | list | tuple | set | frozenset):
        if level >= MAX_SUMMARY_DEPTH:
            return _DROP
        if isinstance(value, Mapping):
            return _clean_mapping(value, level + 1)
        items = sorted(value, key=str) if isinstance(value, set | frozenset) else list(value)
        return _clip_list(items, level + 1)
    # Never str() an arbitrary object: its repr may carry secrets or content.
    return f"<{type(value).__name__}>"


def _clean_mapping(mapping: Mapping[Any, Any], level: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_key, raw_value in mapping.items():
        key = str(raw_key.value if isinstance(raw_key, Enum) else raw_key)[:MAX_SUMMARY_STRING]
        if not _key_allowed(key):
            continue
        value = _clean(raw_value, level)
        if value is not _DROP:
            result[key] = value
    return result


def _serialized_size(value: Mapping[str, Any]) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    )


def sanitize_summary(summary: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-safe, redacted copy of ``summary`` (defense in depth).

    * Drops keys, at any depth and case-insensitively, that contain ``key``,
      ``secret``, ``token``, ``password``, ``passwd``, ``authorization``,
      ``auth_header``, ``cookie``, ``credential``, ``prompt``, ``response``,
      ``content``, ``body``, ``headers`` or ``raw`` (the exact key
      ``api_key_id`` is allowed).
    * Truncates strings to 256 characters and lists to 50 items plus a
      ``"…+N more"`` marker. The summary itself is level 1; containers that
      would sit at level 4 or deeper are dropped.
    * UUIDs, dates and enums become strings; non-finite floats become null;
      any other object becomes ``"<TypeName>"`` (never its ``str()``).
    * If the result serializes to more than 4 KB it is replaced by
      ``{"truncated": true, "field_count": n, "fields": [<top-level key names>]}``,
      where ``fields`` holds as many leading names (each clipped to 64
      characters, at most 50) as fit, so the fallback is itself within 4 KB.
    """
    if not summary:
        return {}
    cleaned = _clean_mapping(summary, 1)
    if _serialized_size(cleaned) <= MAX_SUMMARY_BYTES:
        return cleaned
    return _oversized_fallback(list(cleaned))


def _oversized_fallback(names: list[str]) -> dict[str, Any]:
    """Field names only, built under the same serialized byte budget."""
    fields: list[str] = []
    fallback: dict[str, Any] = {"truncated": True, "field_count": len(names), "fields": fields}
    for name in names[:MAX_SUMMARY_LIST]:
        fields.append(name[:_MAX_FALLBACK_FIELD_NAME])
        if _serialized_size(fallback) > MAX_SUMMARY_BYTES:
            fields.pop()
            break
    return fallback


# ── Writing events ─────────────────────────────────────────────────────────


def _clip(value: object, limit: int) -> str | None:
    return None if value is None else str(value)[:limit]


def _build_event(
    *,
    actor: Actor,
    action: str,
    resource_type: str,
    resource_id: object,
    resource_label: object,
    outcome: AuditOutcome | str,
    summary: Mapping[str, Any] | None,
) -> AuditEvent:
    expected = ACTION_CATALOG.get(action)
    if expected is None:
        raise ValueError(f"Unknown audit action {action!r}; add it to ACTION_CATALOG")
    if resource_type != expected:
        raise ValueError(
            f"Audit action {action!r} uses resource_type {expected!r}, not {resource_type!r}"
        )
    return AuditEvent(
        id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        actor_type=ActorType(actor.type).value,
        actor_id=_clip(actor.id, 64),
        actor_label=_clip(actor.label, 255),
        action=action,
        resource_type=resource_type,
        resource_id=_clip(resource_id, 64),
        resource_label=_clip(resource_label, 255),
        outcome=AuditOutcome(outcome).value,
        summary=sanitize_summary(summary),
    )


def record(
    db: AsyncSession,
    *,
    actor: Actor,
    action: str,
    resource_type: str,
    resource_id: object = None,
    resource_label: object = None,
    outcome: AuditOutcome = AuditOutcome.SUCCEEDED,
    summary: Mapping[str, Any] | None = None,
) -> AuditEvent:
    """Add an event to the caller's session: no flush, no commit.

    Call it before the route's ``await db.commit()`` so the event commits with
    the mutation or not at all. ``resource_id`` may be a UUID or string.
    """
    event = _build_event(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=outcome,
        summary=summary,
    )
    db.add(event)
    return event


SessionContextFactory = Callable[[], AbstractAsyncContextManager["AsyncSession"]]

#: Test hook: when set, independent writes open sessions with this callable
#: instead of :data:`cti.core.database.async_session_factory`.
_session_factory: SessionContextFactory | None = None


def _independent_session() -> AbstractAsyncContextManager[AsyncSession]:
    if _session_factory is not None:
        return _session_factory()
    from cti.core import database  # Late import: keeps engine creation lazy for importers.

    return database.async_session_factory()


async def record_independent(
    *,
    actor: Actor,
    action: str,
    resource_type: str,
    resource_id: object = None,
    resource_label: object = None,
    outcome: AuditOutcome,
    summary: Mapping[str, Any] | None = None,
    strict: bool,
) -> uuid.UUID | None:
    """Write an event in its own session and commit it; return its id.

    ``strict=True`` raises :class:`AuditWriteError` if the write fails (use it
    when the action must not proceed unaudited). ``strict=False`` logs at ERROR
    (action, outcome and exception class only) and returns ``None``.
    Catalog violations raise ``ValueError`` in both modes.
    """
    event = _build_event(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        outcome=outcome,
        summary=summary,
    )
    event_id = event.id
    try:
        async with _independent_session() as session:
            session.add(event)
            await session.commit()
    except Exception as exc:
        if strict:
            raise AuditWriteError("Audit log unavailable") from exc
        logger.error(
            "Audit write failed: action=%s outcome=%s error=%s",
            action,
            event.outcome,
            type(exc).__name__,
        )
        return None
    return event_id


# ── Admin guard with denied events ─────────────────────────────────────────


def audited_admin(
    action: str,
    resource_type: str,
    *,
    resource_id_param: str | None = None,
) -> Callable[..., Awaitable[AuthSubject]]:
    """Dependency like ``require_admin`` that records a ``denied`` event first.

    A non-admin user gets ``{"reason": "not_admin", "status": 403}`` recorded
    (non-strict) and then the same 403 as ``require_admin``. Unauthenticated
    requests (401) are not audited. ``resource_id_param`` names a path
    parameter to use as the event's ``resource_id``.
    """
    if ACTION_CATALOG.get(action) != resource_type:
        raise ValueError(f"Unknown audit action/resource pair {action!r}/{resource_type!r}")

    async def dependency(
        request: Request,
        auth: AuthSubject = Depends(get_current_auth),
    ) -> AuthSubject:
        try:
            return await require_admin(auth)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_403_FORBIDDEN:
                raise
            resource_id = request.path_params.get(resource_id_param) if resource_id_param else None
            await record_independent(
                actor=actor_from_auth(auth),
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=AuditOutcome.DENIED,
                summary={"reason": "not_admin", "status": exc.status_code},
                strict=False,
            )
            raise

    return dependency


# ── Disclosures ────────────────────────────────────────────────────────────

AUDIT_UNAVAILABLE = "Audit log unavailable"


@dataclass(frozen=True)
class Disclosure:
    """A disclosure whose ``initiated`` event has been durably recorded."""

    event_id: uuid.UUID
    actor: Actor
    action: str
    resource_type: str
    resource_id: str | None
    resource_label: str | None

    async def record_outcome(
        self, outcome: AuditOutcome, summary: Mapping[str, Any] | None = None
    ) -> uuid.UUID | None:
        """Record the outcome (non-strict), linked by ``initiated_event_id``."""
        return await record_independent(
            actor=self.actor,
            action=self.action,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            resource_label=self.resource_label,
            outcome=outcome,
            summary={**(summary or {}), "initiated_event_id": str(self.event_id)},
            strict=False,
        )


async def begin_disclosure(
    *,
    actor: Actor,
    action: str,
    resource_type: str,
    resource_id: object = None,
    resource_label: object = None,
    summary: Mapping[str, Any] | None = None,
) -> Disclosure:
    """Durably record ``initiated`` before anything leaves; fail closed.

    Raises ``HTTPException(503, "Audit log unavailable")`` when the write fails,
    so call it before producing any response body.
    """
    try:
        event_id = await record_independent(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
            outcome=AuditOutcome.INITIATED,
            summary=summary,
            strict=True,
        )
    except AuditWriteError:
        logger.error("Disclosure refused: audit log unavailable (action=%s)", action)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=AUDIT_UNAVAILABLE
        ) from None
    assert event_id is not None  # strict writes return an id or raise
    return Disclosure(
        event_id=event_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=_clip(resource_id, 64),
        resource_label=_clip(resource_label, 255),
    )


# Strong references for outcome writes that outlive a cancelled request.
_pending_writes: set[asyncio.Task[Any]] = set()


async def _reap(task: asyncio.Future[Any]) -> None:
    """Cancel ``task`` and wait for it to finish, without raising its result."""
    task.cancel()
    with anyio.CancelScope(shield=True):
        await asyncio.wait({task})


class AuditedDownload(Response):
    """A ``Response`` that records whether its body was handed to the server.

    It records ``completed`` only when every chunk's ASGI ``send`` returned and
    no client disconnect had been observed by the time the final ``send``
    returned. Otherwise it records ``interrupted``: on an observed disconnect
    (it then stops sending) or when sending raises (including
    ``asyncio.CancelledError``, which is re-raised). Both carry
    ``initiated_event_id`` and ``bytes_sent``, which counts only chunks whose
    ``send`` returned with no disconnect observed. ``completed`` does not prove
    the client received it.

    Servers such as uvicorn make ``send`` a silent no-op once the client is
    gone, and may not suspend in it at all, so a watcher task consumes
    ``receive()`` and the sender yields to it before every ``send`` and checks
    its flag, synchronously, right after every ``send`` returns. The
    ``http.disconnect`` a server reports after a completed response is never
    looked at: by then the outcome is settled. For ``HEAD`` the body is not
    sent: ``bytes_sent`` is 0 and ``completed`` means the headers were.
    """

    def __init__(
        self,
        content: Any = None,
        *,
        disclosure: Disclosure,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        chunk_size: int = 64 * 1024,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        super().__init__(
            content=content, status_code=status_code, headers=headers, media_type=media_type
        )
        self.disclosure = disclosure
        self.chunk_size = chunk_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        sent = 0
        delivered = False
        disconnected = asyncio.Event()

        async def watch_disconnect() -> None:
            try:
                while (await receive())["type"] != "http.disconnect":
                    pass
            except Exception:  # A broken receive channel means the client is gone too.
                pass
            disconnected.set()

        async def send_unless_disconnected(message: Message) -> bool:
            # Yield first so the watcher can observe a connection that is
            # already gone; check right after ``send`` returns, with no await
            # in between, so a disconnect observed during the send (e.g. while
            # it waited for flow control) is never taken for delivery.
            await asyncio.sleep(0)
            if disconnected.is_set():
                return False
            await send(message)
            return not disconnected.is_set()

        head_only = scope.get("method") == "HEAD"
        body = b"" if head_only else bytes(self.body)
        starts: Sequence[int] = range(0, len(body), self.chunk_size) or (0,)
        watcher = asyncio.ensure_future(watch_disconnect())
        try:
            try:
                start_message = {
                    "type": "http.response.start",
                    "status": self.status_code,
                    "headers": self.raw_headers,
                }
                if await send_unless_disconnected(start_message):
                    for start in starts:
                        chunk = body[start : start + self.chunk_size]
                        last = start + self.chunk_size >= len(body)
                        message = {
                            "type": "http.response.body",
                            "body": chunk,
                            "more_body": not last,
                        }
                        if not await send_unless_disconnected(message):
                            break
                        sent += len(chunk)
                        delivered = last
            finally:
                await _reap(watcher)
        except BaseException:
            await self._record(AuditOutcome.INTERRUPTED, sent, cancelled_ok=True)
            raise
        await self._record(
            AuditOutcome.COMPLETED if delivered else AuditOutcome.INTERRUPTED,
            sent,
            cancelled_ok=False,
        )
        if delivered and self.background is not None:
            await self.background()

    async def _record(self, outcome: AuditOutcome, sent: int, *, cancelled_ok: bool) -> None:
        # Run in its own task, shielded: a cancelled request must still record.
        task = asyncio.ensure_future(self.disclosure.record_outcome(outcome, {"bytes_sent": sent}))
        _pending_writes.add(task)
        task.add_done_callback(_pending_writes.discard)
        try:
            with anyio.CancelScope(shield=True):
                await asyncio.shield(task)
        except asyncio.CancelledError:
            if not cancelled_ok:
                raise


# ── Reading and retention ──────────────────────────────────────────────────


def as_utc(value: datetime) -> datetime:
    """Normalize to aware UTC; naive values are taken to be UTC already."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def list_events(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    actor_type: ActorType | None = None,
    actor_id: str | None = None,
    actions: Sequence[str] | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcomes: Sequence[AuditOutcome] | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AuditEvent], int]:
    """Filtered page of events, newest first (``occurred_at DESC, id DESC``).

    ``since`` is inclusive and ``until`` exclusive; repeated ``actions`` and
    ``outcomes`` match any of the given values exactly.
    """
    conditions = []
    if since is not None:
        conditions.append(AuditEvent.occurred_at >= as_utc(since))
    if until is not None:
        conditions.append(AuditEvent.occurred_at < as_utc(until))
    if actor_type is not None:
        conditions.append(AuditEvent.actor_type == ActorType(actor_type).value)
    if actor_id is not None:
        conditions.append(AuditEvent.actor_id == actor_id)
    if actions:
        conditions.append(AuditEvent.action.in_(list(actions)))
    if resource_type is not None:
        conditions.append(AuditEvent.resource_type == resource_type)
    if resource_id is not None:
        conditions.append(AuditEvent.resource_id == resource_id)
    if outcomes:
        conditions.append(AuditEvent.outcome.in_([AuditOutcome(o).value for o in outcomes]))

    total = await db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions))
    rows = await db.scalars(
        select(AuditEvent)
        .where(*conditions)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows.all()), int(total or 0)


def validate_retention_days(retention_days: int) -> int:
    if not AUDIT_RETENTION_MIN_DAYS <= retention_days <= AUDIT_RETENTION_MAX_DAYS:
        raise ValueError(
            f"audit retention_days must be between {AUDIT_RETENTION_MIN_DAYS} and "
            f"{AUDIT_RETENTION_MAX_DAYS}"
        )
    return retention_days


def retention_cutoff(retention_days: int, now: datetime | None = None) -> datetime:
    """Events strictly older than this instant are expired."""
    validate_retention_days(retention_days)
    return as_utc(now or datetime.now(UTC)) - timedelta(days=retention_days)


async def purge_expired_events(
    db: AsyncSession,
    retention_days: int,
    *,
    now: datetime | None = None,
    batch_size: int = AUDIT_RETENTION_BATCH_SIZE,
) -> int:
    """Delete events older than the retention window, committing each batch.

    The only code path that deletes audit events. Use a dedicated session:
    this function owns commits and rollback. Raises :class:`AuditRetentionError`
    (carrying the committed count) if a batch fails.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    cutoff = retention_cutoff(retention_days, now)
    total = 0
    while True:
        try:
            ids = list(
                (
                    await db.scalars(
                        select(AuditEvent.id)
                        .where(AuditEvent.occurred_at < cutoff)
                        .order_by(AuditEvent.occurred_at, AuditEvent.id)
                        .limit(batch_size)
                    )
                ).all()
            )
            if not ids:
                await db.rollback()  # Release the read transaction.
                break
            await db.execute(delete(AuditEvent).where(AuditEvent.id.in_(ids)))
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(
                "Audit retention batch failed after %d deletions (%s)",
                total,
                type(exc).__name__,
            )
            raise AuditRetentionError(total) from exc
        total += len(ids)
    if total:
        logger.info("Audit retention removed %d events older than %d days", total, retention_days)
    return total
