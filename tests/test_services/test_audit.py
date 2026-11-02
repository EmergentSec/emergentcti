"""Audit core: sanitization, transactional semantics, attribution, retention."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from cti.core.config import Settings
from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.api_key import ApiKey
from cti.models.audit import AuditEvent
from cti.models.observable import ObservableType
from cti.models.user import User, UserRole
from cti.services import audit, scheduler
from cti.services.audit import Actor, ActorType, AuditOutcome
from tests.conftest import TestSessionFactory

ADMIN = Actor(ActorType.USER, str(uuid.uuid4()), "admin")


async def events(db) -> list[AuditEvent]:
    return list((await db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at))).all())


async def count(db, model) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


def allowlist_entry(value: str = "10.0.0.1") -> AllowlistEntry:
    return AllowlistEntry(
        kind=AllowlistKind.EXACT,
        value=value,
        observable_type=ObservableType.IP_ADDR,
        reason="known good",
    )


# ── sanitize_summary ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "API_KEY",
        "x_api_key",
        "client_secret",
        "access_token",
        "Password",
        "new_passwd",
        "Authorization",
        "auth_header",
        "set_cookie",
        "credentials",
        "system_prompt",
        "response_text",
        "content",
        "body",
        "request_headers",
        "raw_error",
    ],
)
def test_sanitize_drops_sensitive_keys_at_any_depth(key: str) -> None:
    summary = {key: "s3cret", "nested": {"inner": {key: "s3cret", "ok": 1}}, "list": [{key: 1}]}
    cleaned = audit.sanitize_summary(summary)
    assert "s3cret" not in json.dumps(cleaned)
    assert cleaned == {"nested": {"inner": {"ok": 1}}, "list": [{}]}


def test_sanitize_keeps_exact_api_key_id_only() -> None:
    cleaned = audit.sanitize_summary({"api_key_id": "abc", "API_KEY_ID": "x", "api_key_ids": "y"})
    assert cleaned == {"api_key_id": "abc"}


def test_sanitize_truncates_strings_lists_and_depth() -> None:
    cleaned = audit.sanitize_summary(
        {
            "long": "x" * 1000,
            "many": list(range(120)),
            "deep": {"two": {"three": {"four": 1}, "keep": "y"}},
            "deep_list": [[[1]]],
        }
    )
    assert cleaned["long"] == "x" * 256
    assert cleaned["many"] == [*range(50), "…+70 more"]
    assert cleaned["deep"] == {"two": {"keep": "y"}}
    assert cleaned["deep_list"] == [[]]


def test_sanitize_converts_types_and_never_stringifies_objects() -> None:
    marker = uuid.uuid4()

    class Leaky:
        def __repr__(self) -> str:
            return "Leaky(secret='hunter2')"

        __str__ = __repr__

    cleaned = audit.sanitize_summary(
        {
            "id": marker,
            "at": datetime(2026, 11, 2, tzinfo=UTC),
            "outcome": AuditOutcome.FAILED,
            "nan": float("nan"),
            "blob": b"bytes",
            "obj": Leaky(),
            "set": {"b", "a"},
            1: "int key",
        }
    )
    assert cleaned == {
        "id": str(marker),
        "at": "2026-11-02T00:00:00+00:00",
        "outcome": "failed",
        "nan": None,
        "blob": "<bytes>",
        "obj": "<Leaky>",
        "set": ["a", "b"],
        "1": "int key",
    }
    json.dumps(cleaned, allow_nan=False)


def test_sanitize_oversized_summary_keeps_only_field_names() -> None:
    summary = {f"field_{i}": "v" * 200 for i in range(40)}
    cleaned = audit.sanitize_summary(summary)
    assert cleaned["truncated"] is True
    assert cleaned["fields"][:2] == ["field_0", "field_1"]
    assert len(json.dumps(cleaned).encode()) <= audit.MAX_SUMMARY_BYTES
    huge_keys = audit.sanitize_summary({("k" * 200) + str(i): i for i in range(500)})
    # Every key above contains "k"... but not the denied "key" substring.
    assert huge_keys["truncated"] is True
    assert len(json.dumps(huge_keys, ensure_ascii=False).encode()) <= audit.MAX_SUMMARY_BYTES


def test_sanitize_empty() -> None:
    assert audit.sanitize_summary(None) == {}
    assert audit.sanitize_summary({}) == {}


# ── actors ─────────────────────────────────────────────────────────────────


async def test_actor_from_auth_uses_record_ids_and_names(db_session, test_api_key) -> None:
    raw_key, key_hash = test_api_key
    key = ApiKey(name="Firewall", key_hash=key_hash, key_prefix=raw_key[:12])
    user = User(username="alice", password_hash="x", role=UserRole.admin)
    db_session.add_all([key, user])
    await db_session.commit()

    assert audit.actor_from_auth(key) == Actor(ActorType.API_KEY, str(key.id), "Firewall")
    assert audit.actor_from_auth(user) == Actor(ActorType.USER, str(user.id), "alice")
    # After a rollback the instance is expired; no lazy load (MissingGreenlet).
    await db_session.rollback()
    assert audit.actor_from_auth(key).id == str(key.id)
    assert audit.system_actor("system:x", "X") == Actor(ActorType.SYSTEM, "system:x", "X")


# ── record(): same transaction ─────────────────────────────────────────────


async def test_record_commits_with_mutation(db_session) -> None:
    entry = allowlist_entry()
    db_session.add(entry)
    await db_session.flush()
    event = audit.record(
        db_session,
        actor=ADMIN,
        action="allowlist.create",
        resource_type="allowlist_entry",
        resource_id=entry.id,
        resource_label=entry.value,
        summary={"kind": "exact"},
    )
    await db_session.commit()
    [stored] = await events(db_session)
    assert stored.id == event.id
    assert (stored.outcome, stored.resource_id, stored.summary) == (
        "succeeded",
        str(entry.id),
        {"kind": "exact"},
    )


async def test_record_rollback_produces_no_event(db_session) -> None:
    db_session.add(allowlist_entry())
    audit.record(
        db_session, actor=ADMIN, action="allowlist.create", resource_type="allowlist_entry"
    )
    await db_session.rollback()
    assert await events(db_session) == []
    assert await count(db_session, AllowlistEntry) == 0


async def test_failing_audit_insert_rolls_back_sibling_mutation(db_session) -> None:
    db_session.add(allowlist_entry())
    event = audit.record(
        db_session, actor=ADMIN, action="allowlist.create", resource_type="allowlist_entry"
    )
    event.action = None  # type: ignore[assignment]  # simulate a failing audit insert
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert await count(db_session, AllowlistEntry) == 0
    assert await events(db_session) == []


def test_record_rejects_unknown_action_or_resource_type(db_session) -> None:
    with pytest.raises(ValueError, match="Unknown audit action"):
        audit.record(db_session, actor=ADMIN, action="allowlist.edit", resource_type="x")
    with pytest.raises(ValueError, match="resource_type"):
        audit.record(db_session, actor=ADMIN, action="allowlist.create", resource_type="report")


async def test_record_clips_identifiers_and_labels(db_session) -> None:
    audit.record(
        db_session,
        actor=Actor(ActorType.USER, "u" * 100, "n" * 400),
        action="report.update",
        resource_type="report",
        resource_id="r" * 100,
        resource_label="t" * 400,
    )
    await db_session.commit()
    [stored] = await events(db_session)
    assert (len(stored.actor_id), len(stored.actor_label)) == (64, 255)
    assert (len(stored.resource_id), len(stored.resource_label)) == (64, 255)


# ── record_independent(): own session ──────────────────────────────────────


@pytest.mark.usefixtures("separate_audit_sessions")
async def test_record_independent_survives_caller_rollback(db_session) -> None:
    db_session.add(allowlist_entry())
    await db_session.flush()
    await db_session.rollback()  # the request transaction is doomed: roll back first
    event_id = await audit.record_independent(
        actor=ADMIN,
        action="allowlist.create",
        resource_type="allowlist_entry",
        outcome=AuditOutcome.FAILED,
        summary={"reason": "duplicate", "status": 409},
        strict=True,
    )
    [stored] = await events(db_session)
    assert stored.id == event_id
    assert stored.outcome == "failed"
    assert stored.summary == {"reason": "duplicate", "status": 409}
    assert await count(db_session, AllowlistEntry) == 0


@pytest.mark.usefixtures("separate_audit_sessions")
async def test_record_independent_is_committed_before_caller_commits(db_session) -> None:
    await audit.record_independent(
        actor=ADMIN,
        action="export.download",
        resource_type="export",
        resource_id="json",
        outcome=AuditOutcome.INITIATED,
        strict=True,
    )
    # A brand-new session sees it: it was committed on its own connection.
    async with TestSessionFactory() as other:
        assert [e.outcome for e in await events(other)] == ["initiated"]


class _BrokenSession:
    def add(self, _obj: object) -> None:
        return None

    async def commit(self) -> None:
        raise RuntimeError("INSERT failed with params ('Bearer s3cret',)")

    async def __aenter__(self) -> _BrokenSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


async def test_record_independent_strict_raises(monkeypatch) -> None:
    monkeypatch.setattr(audit, "_session_factory", _BrokenSession)
    with pytest.raises(audit.AuditWriteError):
        await audit.record_independent(
            actor=ADMIN,
            action="export.download",
            resource_type="export",
            outcome=AuditOutcome.INITIATED,
            strict=True,
        )


async def test_record_independent_non_strict_logs_without_contents(monkeypatch, caplog) -> None:
    monkeypatch.setattr(audit, "_session_factory", _BrokenSession)
    caplog.set_level(logging.DEBUG)
    result = await audit.record_independent(
        actor=ADMIN,
        action="feed.update",
        resource_type="feed",
        outcome=AuditOutcome.FAILED,
        summary={"reason": "summary-marker-value"},
        strict=False,
    )
    assert result is None
    [record] = [r for r in caplog.records if r.name == "cti.services.audit"]
    assert record.levelno == logging.ERROR
    assert "feed.update" in caplog.text and "RuntimeError" in caplog.text
    assert "summary-marker-value" not in caplog.text
    assert "s3cret" not in caplog.text  # exception messages carry bound params
    assert record.exc_info is None


async def test_record_independent_rejects_catalog_violation_even_non_strict() -> None:
    with pytest.raises(ValueError):
        await audit.record_independent(
            actor=ADMIN, action="nope", resource_type="x", outcome=AuditOutcome.FAILED, strict=False
        )


# ── deletion keeps history; API-key attribution ────────────────────────────


async def test_deleting_actor_user_and_api_key_keeps_history(db_session, test_api_key) -> None:
    raw_key, key_hash = test_api_key
    key = ApiKey(name="SIEM pull", key_hash=key_hash, key_prefix=raw_key[:12])
    user = User(username="carol", password_hash="x", role=UserRole.admin)
    entry = allowlist_entry("10.9.9.9")
    db_session.add_all([key, user, entry])
    await db_session.commit()
    user_id, key_id, entry_id = str(user.id), str(key.id), str(entry.id)

    for actor in (audit.actor_from_auth(user), audit.actor_from_auth(key)):
        audit.record(
            db_session,
            actor=actor,
            action="allowlist.delete",
            resource_type="allowlist_entry",
            resource_id=entry_id,
            resource_label=entry.value,
        )
    await db_session.commit()

    for obj in (user, key, entry):
        await db_session.delete(obj)
    await db_session.commit()
    db_session.expunge_all()

    stored = await events(db_session)
    assert {(e.actor_type, e.actor_id, e.actor_label) for e in stored} == {
        ("user", user_id, "carol"),
        ("api_key", key_id, "SIEM pull"),
    }
    assert {(e.resource_id, e.resource_label) for e in stored} == {(entry_id, "10.9.9.9")}
    # The raw key and its hash appear nowhere in any stored row.
    rows = (await db_session.execute(select(AuditEvent.__table__))).all()
    dumped = json.dumps([list(r) for r in rows], default=str)
    assert raw_key not in dumped and key_hash not in dumped and raw_key[:12] not in dumped


def test_audit_table_has_no_foreign_keys() -> None:
    assert not AuditEvent.__table__.foreign_keys


# ── retention ──────────────────────────────────────────────────────────────

NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)


def aged(days: float, action: str = "report.update", *, now: datetime = NOW) -> AuditEvent:
    event = audit._build_event(
        actor=ADMIN,
        action=action,
        resource_type=audit.ACTION_CATALOG[action],
        resource_id=None,
        resource_label=None,
        outcome=AuditOutcome.SUCCEEDED,
        summary=None,
    )
    event.occurred_at = now - timedelta(days=days)
    return event


@pytest.mark.parametrize("days", [29, 0, -1, 3651])
def test_retention_bounds_rejected(days: int) -> None:
    with pytest.raises(ValidationError):
        Settings(AUDIT_RETENTION_DAYS=days, _env_file=None)
    with pytest.raises(ValueError, match="between 30 and 3650"):
        audit.retention_cutoff(days)


def test_retention_defaults_and_bounds_accepted() -> None:
    assert Settings(_env_file=None).AUDIT_RETENTION_DAYS == 365
    for days in (30, 3650):
        settings = Settings(AUDIT_RETENTION_DAYS=days, _env_file=None)
        assert days == settings.AUDIT_RETENTION_DAYS


async def test_purge_deletes_strictly_older_in_batches(db_session, monkeypatch) -> None:
    db_session.add_all([aged(31), aged(40), aged(400), aged(30), aged(29), aged(1, "feed.delete")])
    await db_session.commit()
    commits = 0
    real_commit = db_session.commit

    async def counting_commit() -> None:
        nonlocal commits
        commits += 1
        await real_commit()

    monkeypatch.setattr(db_session, "commit", counting_commit)
    deleted = await audit.purge_expired_events(db_session, 30, now=NOW, batch_size=2)
    assert deleted == 3
    assert commits == 2  # batches of 2 then 1, a commit per batch
    stored = await events(db_session)
    remaining = sorted((NOW - audit.as_utc(e.occurred_at)).days for e in stored)
    assert remaining == [1, 29, 30]
    assert await audit.purge_expired_events(db_session, 30, now=NOW) == 0


async def test_purge_failure_reports_committed_count(db_session, monkeypatch) -> None:
    db_session.add_all([aged(100), aged(200)])
    await db_session.commit()
    real_execute = db_session.execute
    calls = 0

    async def fail_second_delete(stmt, *args, **kwargs):
        nonlocal calls
        if getattr(stmt, "is_delete", False):
            calls += 1
            if calls == 2:
                raise RuntimeError("disk full")
        return await real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", fail_second_delete)
    with pytest.raises(audit.AuditRetentionError) as info:
        await audit.purge_expired_events(db_session, 30, now=NOW, batch_size=1)
    assert info.value.deleted == 1
    assert len(await events(db_session)) == 1


async def test_purge_validates_arguments(db_session) -> None:
    with pytest.raises(ValueError):
        await audit.purge_expired_events(db_session, 29)
    with pytest.raises(ValueError, match="positive"):
        await audit.purge_expired_events(db_session, 30, batch_size=0)


# ── scheduler jobs write one aggregated event per run ──────────────────────


@pytest.fixture
def job_sessions(monkeypatch):
    from cti.core import database

    monkeypatch.setattr(database, "async_session_factory", TestSessionFactory)


@pytest.mark.usefixtures("job_sessions", "separate_audit_sessions")
async def test_audit_retention_job_purges_and_records_one_event(db_session, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "get_settings", lambda: Settings(_env_file=None))
    now = datetime.now(UTC)
    db_session.add_all([aged(days, now=now) for days in (400, 500, 600, 1)])
    await db_session.commit()

    await scheduler._run_audit_retention_job()

    db_session.expunge_all()
    stored = await events(db_session)
    cleanup = [e for e in stored if e.action == "audit.retention_cleanup"]
    assert len(stored) == 2 and len(cleanup) == 1
    [event] = cleanup
    assert (event.actor_type, event.actor_id, event.outcome, event.resource_type) == (
        "system",
        "system:audit_retention",
        "succeeded",
        "audit",
    )
    assert event.summary["deleted"] == 3
    assert datetime.fromisoformat(event.summary["cutoff"]) < datetime.now(UTC) - timedelta(days=364)


@pytest.mark.usefixtures("separate_audit_sessions")
async def test_audit_retention_job_failure_records_failed_event(db_session, monkeypatch) -> None:
    from cti.core import database

    async def boom(*_args, **_kwargs):
        raise audit.AuditRetentionError(7) from RuntimeError("x")

    monkeypatch.setattr(database, "async_session_factory", MagicMock())
    monkeypatch.setattr(audit, "purge_expired_events", boom)
    await scheduler._run_audit_retention_job()
    [event] = await events(db_session)
    assert event.outcome == "failed"
    assert event.summary["deleted"] == 7 and event.summary["error_code"] == "RuntimeError"


@pytest.mark.usefixtures("job_sessions", "separate_audit_sessions")
async def test_observable_retention_job_records_one_aggregated_event(db_session, monkeypatch):
    from cti.services import retention

    async def fake_enforce(_db, days):
        return 1234

    monkeypatch.setattr(retention, "enforce_retention", fake_enforce)
    monkeypatch.setattr(
        scheduler, "get_settings", lambda: Settings(OBSERVABLE_RETENTION_DAYS=90, _env_file=None)
    )
    await scheduler._run_retention_job()
    [event] = await events(db_session)
    assert (event.action, event.actor_id, event.outcome) == (
        "retention.observables_cleanup",
        "system:observable_retention",
        "succeeded",
    )
    assert event.summary == {"deleted": 1234, "retention_days": 90}


@pytest.mark.usefixtures("job_sessions", "separate_audit_sessions")
async def test_observable_retention_job_failure_records_failed_event(db_session, monkeypatch):
    from cti.services import retention

    async def failing(_db, _days):
        raise RuntimeError("boom")

    monkeypatch.setattr(retention, "enforce_retention", failing)
    await scheduler._run_retention_job()
    [event] = await events(db_session)
    assert event.outcome == "failed"
    assert event.summary["error_code"] == "RuntimeError"
    assert "deleted" not in event.summary


async def test_audit_retention_job_registered_daily_at_0330(monkeypatch) -> None:
    sched = MagicMock()
    await scheduler.add_audit_retention_job(sched)
    args, kwargs = sched.add_job.call_args
    assert args[0] is scheduler._run_audit_retention_job
    before = datetime(2026, 11, 2, 3, 29, tzinfo=UTC)
    assert args[1].get_next_fire_time(None, before) == datetime(2026, 11, 2, 3, 30, tzinfo=UTC)
    assert kwargs["id"] == "system:audit_retention"
    assert kwargs["max_instances"] == 1 and kwargs["coalesce"] is True
    # Defaults to the module scheduler.
    monkeypatch.setattr(scheduler, "scheduler", sched)
    await scheduler.add_audit_retention_job()
    assert sched.add_job.call_count == 2
