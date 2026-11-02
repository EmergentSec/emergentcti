"""AuditedDownload delivery outcomes at the ASGI level."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from cti.models.audit import AuditEvent
from cti.services import audit
from cti.services.audit import Actor, ActorType, AuditOutcome

ACTOR = Actor(ActorType.API_KEY, str(uuid.uuid4()), "Firewall")
BODY = b"1.2.3.4\n" * 1000  # 8000 bytes
SCOPE = {"type": "http", "method": "GET", "path": "/x", "headers": []}

pytestmark = pytest.mark.usefixtures("separate_audit_sessions")


async def begin() -> audit.Disclosure:
    return await audit.begin_disclosure(
        actor=ACTOR,
        action="export.download",
        resource_type="export",
        resource_id="blocklist:ip",
        summary={"count": 1000},
    )


async def outcomes(db) -> list[AuditEvent]:
    rows = await db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at))
    return list(rows.all())


async def never_disconnects() -> dict:
    await asyncio.Event().wait()
    return {"type": "http.disconnect"}


async def test_completed_after_final_chunk(db_session) -> None:
    disclosure = await begin()
    messages: list[dict] = []

    async def send(message: dict) -> None:
        messages.append(message)

    response = audit.AuditedDownload(
        BODY, disclosure=disclosure, media_type="text/plain", chunk_size=3000
    )
    await response(SCOPE, never_disconnects, send)

    bodies = [m for m in messages if m["type"] == "http.response.body"]
    assert b"".join(m["body"] for m in bodies) == BODY
    assert [m["more_body"] for m in bodies] == [True, True, False]
    initiated, completed = await outcomes(db_session)
    assert initiated.outcome == "initiated" and initiated.id == disclosure.event_id
    assert completed.outcome == "completed"
    assert completed.summary == {"bytes_sent": 8000, "initiated_event_id": str(initiated.id)}
    assert (completed.action, completed.resource_id, completed.actor_id) == (
        "export.download",
        "blocklist:ip",
        ACTOR.id,
    )


async def test_empty_body_completes(db_session) -> None:
    disclosure = await begin()
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    await audit.AuditedDownload(b"", disclosure=disclosure)(SCOPE, never_disconnects, send)
    assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
    assert [e.outcome for e in await outcomes(db_session)] == ["initiated", "completed"]


@pytest.mark.parametrize("error", [OSError("connection reset"), asyncio.CancelledError()])
async def test_interrupted_when_send_raises_and_reraises(db_session, error) -> None:
    disclosure = await begin()
    calls = 0

    async def send(message: dict) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:  # start, first chunk, then fail on the second chunk
            raise error

    response = audit.AuditedDownload(BODY, disclosure=disclosure, chunk_size=3000)
    with pytest.raises(type(error)):
        await response(SCOPE, never_disconnects, send)

    _, interrupted = await outcomes(db_session)
    assert interrupted.outcome == "interrupted"
    assert interrupted.summary == {
        "bytes_sent": 3000,
        "initiated_event_id": str(disclosure.event_id),
    }


async def test_interrupted_when_task_is_cancelled_mid_send(db_session) -> None:
    disclosure = await begin()
    first_chunk_sent = asyncio.Event()

    async def send(message: dict) -> None:
        if message.get("more_body") is False:
            await asyncio.Event().wait()  # a stalled transport
        if message["type"] == "http.response.body":
            first_chunk_sent.set()

    response = audit.AuditedDownload(BODY, disclosure=disclosure, chunk_size=4000)
    task = asyncio.create_task(response(SCOPE, never_disconnects, send))
    await first_chunk_sent.wait()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _, interrupted = await outcomes(db_session)
    assert interrupted.outcome == "interrupted"
    assert interrupted.summary["bytes_sent"] == 4000


async def test_interrupted_when_client_disconnects(db_session) -> None:
    disclosure = await begin()
    disconnect = asyncio.Event()
    bodies: list[bytes] = []

    async def receive() -> dict:
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.body":
            bodies.append(message["body"])
            disconnect.set()  # the client goes away after the first chunk
        await asyncio.sleep(0)

    response = audit.AuditedDownload(BODY, disclosure=disclosure, chunk_size=2000)
    await response(SCOPE, receive, send)  # no exception: nobody is left to tell

    assert len(bodies) < 4
    _, interrupted = await outcomes(db_session)
    assert interrupted.outcome == "interrupted"
    assert interrupted.summary["bytes_sent"] == sum(len(b) for b in bodies)


async def test_begin_disclosure_fails_closed(monkeypatch, db_session) -> None:
    class Broken:
        def add(self, _obj: object) -> None: ...

        async def commit(self) -> None:
            raise RuntimeError("db down")

        async def __aenter__(self) -> Broken:
            return self

        async def __aexit__(self, *exc: object) -> None: ...

    monkeypatch.setattr(audit, "_session_factory", Broken)
    with pytest.raises(HTTPException) as info:
        await begin()
    assert (info.value.status_code, info.value.detail) == (503, "Audit log unavailable")


async def test_outcome_write_failure_does_not_break_delivery(monkeypatch, db_session) -> None:
    disclosure = await begin()
    sent: list[dict] = []

    async def failing_outcome(*_args, **_kwargs):
        return None  # record_independent(strict=False) already swallowed the failure

    monkeypatch.setattr(disclosure.__class__, "record_outcome", failing_outcome)

    async def send(message: dict) -> None:
        sent.append(message)

    await audit.AuditedDownload(BODY, disclosure=disclosure)(SCOPE, never_disconnects, send)
    assert b"".join(m.get("body", b"") for m in sent) == BODY


def test_chunk_size_validated() -> None:
    disclosure = audit.Disclosure(uuid.uuid4(), ACTOR, "export.download", "export", None, None)
    with pytest.raises(ValueError):
        audit.AuditedDownload(b"x", disclosure=disclosure, chunk_size=0)


async def test_ai_request_initiated_then_outcome(db_session) -> None:
    meta = {"operation": "check", "provider": "openai", "model": "gpt-x"}
    disclosure = await audit.begin_disclosure(
        actor=ACTOR,
        action="ai.request",
        resource_type="ai_provider",
        resource_id="openai",
        summary={**meta, "prompt": "never stored"},
    )
    await disclosure.record_outcome(
        AuditOutcome.FAILED, {**meta, "error_code": "timeout", "response": "never stored"}
    )
    initiated, failed = await outcomes(db_session)
    assert initiated.summary == meta
    assert failed.outcome == "failed"
    assert failed.summary == {
        **meta,
        "error_code": "timeout",
        "initiated_event_id": str(initiated.id),
    }
