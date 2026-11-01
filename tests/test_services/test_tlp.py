"""TLP policy (#15): effective-marking rule (in SQL) and destination gates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import insert, select

from cti.feeds.base import RawObservable
from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.models.report import Report, ReportOrigin, report_observables
from cti.models.tlp import Tlp
from cti.services import observable_service, report_service
from cti.services.tlp import (
    EXTERNAL_AI,
    effective_tlp_map,
    filter_for_external_ai,
    is_downgrade,
    is_shareable,
    more_restrictive,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

N = None  # Unspecified
C, G, A, S, R = Tlp.CLEAR, Tlp.GREEN, Tlp.AMBER, Tlp.AMBER_STRICT, Tlp.RED
ALL_MARKINGS: list[Tlp | None] = [N, C, G, A, S, R]


# ── destination matrix ───────────────────────────────────────────────────

ALLOWED = {
    "internal": {N, C, G, A, S},
    "community": {C, G},
    "public": {C},
    EXTERNAL_AI: {C, G},
}


@pytest.mark.parametrize("destination", sorted(ALLOWED))
@pytest.mark.parametrize("marking", ALL_MARKINGS, ids=lambda m: m or "unspecified")
def test_destination_matrix(destination: str, marking: Tlp | None) -> None:
    assert is_shareable(marking, destination) is (marking in ALLOWED[destination])
    # Stored strings behave exactly like the enum.
    raw = marking.value if marking is not None else None
    assert is_shareable(raw, destination) is (marking in ALLOWED[destination])


@pytest.mark.parametrize("destination", ["", "partners", "INTERNAL", "red", "external-ai"])
@pytest.mark.parametrize("marking", ALL_MARKINGS, ids=lambda m: m or "unspecified")
def test_unknown_destination_fails_closed(destination: str, marking: Tlp | None) -> None:
    assert is_shareable(marking, destination) is False


def test_red_never_shareable_and_garbage_marking_fails_closed() -> None:
    for destination in [*ALLOWED, "anything"]:
        assert is_shareable(R, destination) is False
        assert is_shareable("not-a-marking", destination) is False


def test_downgrade_rule() -> None:
    # Specified -> lower rank or -> Unspecified is a downgrade.
    assert is_downgrade(R, A) and is_downgrade(G, C) and is_downgrade(C, N)
    assert is_downgrade(S, N)
    # Tightening, no change, and initial classification are not.
    assert not is_downgrade(A, R) and not is_downgrade(A, A)
    for marking in ALL_MARKINGS:
        assert not is_downgrade(N, marking)


def test_more_restrictive() -> None:
    assert more_restrictive(N, G) is G
    assert more_restrictive(G, N) is G
    assert more_restrictive(A, G) is A
    assert more_restrictive(G, R) is R
    assert more_restrictive(N, N) is None


# ── effective marking, computed in SQL ───────────────────────────────────


async def _feed(db: AsyncSession, tlp: Tlp | None) -> Feed:
    feed = Feed(name=f"feed-{uuid.uuid4().hex[:8]}", feed_type=FeedType.FILE, tlp=tlp)
    db.add(feed)
    await db.flush()
    return feed


async def _report(db: AsyncSession, tlp: Tlp | None) -> Report:
    report = Report(title=f"r-{uuid.uuid4().hex[:8]}", origin=ReportOrigin.INTERNAL, tlp=tlp)
    db.add(report)
    await db.flush()
    return report


async def _observable(
    db: AsyncSession,
    *,
    feeds: list[Tlp | None] = (),  # type: ignore[assignment]
    reports: list[Tlp | None] = (),  # type: ignore[assignment]
    manual: Tlp | None = None,
    override: Tlp | None = None,
) -> Observable:
    now = datetime.now(UTC)
    obs = Observable(
        type=ObservableType.DOMAIN_NAME,
        value=f"{uuid.uuid4().hex[:10]}.example",
        manual_tlp=manual,
        first_seen=now,
        last_seen=now,
    )
    if override is not None:
        obs.tlp_override = override
        obs.tlp_override_reason = "test"
        obs.tlp_override_set_at = now
    db.add(obs)
    await db.flush()
    for marking in feeds:
        feed = await _feed(db, marking)
        db.add(ObservableSource(observable_id=obs.id, feed_id=feed.id))
    for marking in reports:
        report = await _report(db, marking)
        await db.execute(
            insert(report_observables).values(report_id=report.id, observable_id=obs.id)
        )
    await db.flush()
    return obs


async def _effective(db: AsyncSession, obs: Observable) -> Tlp | None:
    return (await effective_tlp_map(db, [obs.id]))[obs.id]


EFFECTIVE_CASES = [
    # (feeds, reports, manual, override, expected)
    pytest.param([], [], N, N, N, id="manual-only-unspecified"),
    pytest.param([], [], G, N, G, id="manual-only-green"),
    pytest.param([C], [], N, N, C, id="feed-only-clear: manual NULL ignored"),
    pytest.param([R], [], N, N, R, id="feed-only-red"),
    pytest.param([N], [], N, N, N, id="feed-only-unspecified"),
    pytest.param([C, G], [], N, N, G, id="multi-feed most restrictive"),
    pytest.param([G], [A], N, N, A, id="report raises feed"),
    pytest.param([A], [C], N, N, A, id="feed raises report"),
    pytest.param([C, N], [], N, N, N, id="unspecified poisons clear"),
    pytest.param([G], [N], N, N, N, id="unspecified report poisons green"),
    pytest.param([A, N], [], N, N, A, id="amber dominates unspecified"),
    pytest.param([N], [S], N, N, S, id="amber+strict dominates unspecified"),
    pytest.param([N, R], [], N, N, R, id="red dominates unspecified"),
    pytest.param([C], [], A, N, A, id="manual input counts when set"),
    pytest.param([R], [], C, N, R, id="manual cannot loosen"),
    pytest.param([], [G], N, N, G, id="report-only: manual NULL ignored"),
    pytest.param([R], [R], N, C, C, id="override loosens"),
    pytest.param([C], [], N, R, R, id="override tightens"),
    pytest.param([N], [], N, G, G, id="override beats unspecified"),
    pytest.param([C, G], [C, A], G, N, A, id="many inputs"),
]


@pytest.mark.parametrize(("feeds", "reports", "manual", "override", "expected"), EFFECTIVE_CASES)
async def test_effective_marking_rule(
    db_session: AsyncSession,
    feeds: list[Tlp | None],
    reports: list[Tlp | None],
    manual: Tlp | None,
    override: Tlp | None,
    expected: Tlp | None,
) -> None:
    obs = await _observable(
        db_session, feeds=feeds, reports=reports, manual=manual, override=override
    )
    assert await _effective(db_session, obs) == expected


async def test_override_clear_restores_input_rule(db_session: AsyncSession) -> None:
    obs = await _observable(db_session, feeds=[R])
    await observable_service.set_tlp_override(db_session, obs.id, C, "declassified", set_by_id=None)
    assert await _effective(db_session, obs) is C
    await observable_service.clear_tlp_override(db_session, obs.id)
    assert await _effective(db_session, obs) is R


async def test_effective_marking_is_read_time_not_stored(db_session: AsyncSession) -> None:
    feed = await _feed(db_session, G)
    obs = await _observable(db_session)
    db_session.add(ObservableSource(observable_id=obs.id, feed_id=feed.id))
    await db_session.flush()
    assert await _effective(db_session, obs) is G
    feed.tlp = R.value
    await db_session.flush()
    assert await _effective(db_session, obs) is R


# ── imports, feed runs and new links cannot downgrade ────────────────────


async def test_feed_run_cannot_downgrade(db_session: AsyncSession) -> None:
    red_feed = await _feed(db_session, R)
    clear_feed = await _feed(db_session, C)
    raw = [RawObservable(type=ObservableType.IP_ADDR, value="198.51.100.7")]
    await observable_service.bulk_upsert_from_feed(db_session, red_feed, raw)
    await observable_service.bulk_upsert_from_feed(db_session, clear_feed, raw)
    obs_id = await db_session.scalar(
        select(Observable.id).where(Observable.value == "198.51.100.7")
    )
    assert obs_id is not None
    assert (await effective_tlp_map(db_session, [obs_id]))[obs_id] is R


async def test_unspecified_feed_run_cannot_make_amber_shareable(db_session: AsyncSession) -> None:
    obs = await _observable(db_session, reports=[A])
    unspecified_feed = await _feed(db_session, N)
    await observable_service.bulk_upsert_from_feed(
        db_session, unspecified_feed, [RawObservable(type=obs.type, value=obs.value)]
    )
    assert await _effective(db_session, obs) is A


async def test_new_report_link_cannot_downgrade(db_session: AsyncSession) -> None:
    obs = await _observable(db_session, feeds=[S])
    clear_report = await _report(db_session, C)
    await report_service.link_observable(db_session, clear_report.id, obs.id)
    assert await _effective(db_session, obs) is S


async def test_manual_recreate_keeps_more_restrictive(db_session: AsyncSession) -> None:
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/a", tlp=A
    )
    assert obs.manual_tlp == "amber"
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/a", tlp=C
    )
    assert obs.manual_tlp == "amber"
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/a", tlp=None
    )
    assert obs.manual_tlp == "amber"
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/a", tlp=R
    )
    assert obs.manual_tlp == "red"


async def test_manual_recreate_specified_replaces_null(db_session: AsyncSession) -> None:
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/b"
    )
    assert obs.manual_tlp is None
    obs, _ = await observable_service.create_observable(
        db_session, ObservableType.URL, "https://evil.example/b", tlp=C
    )
    assert obs.manual_tlp == "clear"


# ── external AI gate ─────────────────────────────────────────────────────


async def test_filter_for_external_ai(db_session: AsyncSession) -> None:
    keep_obs = await _observable(db_session, manual=G)
    drop_unspecified = await _observable(db_session)
    drop_amber = await _observable(db_session, feeds=[A])
    drop_red = await _observable(db_session, feeds=[C], override=R)
    keep_report = await _report(db_session, C)
    drop_report = await _report(db_session, None)
    drop_red_report = await _report(db_session, R)

    kept = await filter_for_external_ai(
        db_session,
        [keep_obs, drop_unspecified, drop_amber, drop_red],
    )
    assert kept == [keep_obs]
    kept_reports = await filter_for_external_ai(
        db_session, [keep_report, drop_report, drop_red_report]
    )
    assert kept_reports == [keep_report]
