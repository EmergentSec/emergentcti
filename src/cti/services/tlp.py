"""TLP sharing policy (#15): effective markings and destination gates.

This module owns both rules:

* :func:`effective_tlp_expr` — the *effective marking* of an observable,
  computed in SQL at read/export time (never stored, so it cannot drift).
* :func:`is_shareable` / :func:`shareable_clause` — whether an effective
  marking may leave to a destination. Both derive from one table,
  ``_ALLOWED``.

TLP is a sharing policy, not access control: every authenticated user can
still view every marking in the app.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, case, false, func, literal, or_, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import FunctionElement

from cti.models.feed import Feed
from cti.models.observable import Observable
from cti.models.observable_source import ObservableSource
from cti.models.report import Report, report_observables
from cti.models.tlp import TLP_RANK, UNSPECIFIED, Tlp

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

logger = logging.getLogger(__name__)

# Code-only destination for any future feature that sends instance data to an
# external AI provider. It is deliberately not an export-profile option.
EXTERNAL_AI = "external_ai"

# destination → effective markings allowed to leave. ``None`` = Unspecified.
# RED is in no set: it never leaves through any export, profile or API key.
_ALLOWED: dict[str, frozenset[Tlp | None]] = {
    "internal": frozenset({None, Tlp.CLEAR, Tlp.GREEN, Tlp.AMBER, Tlp.AMBER_STRICT}),
    "community": frozenset({Tlp.CLEAR, Tlp.GREEN}),
    "public": frozenset({Tlp.CLEAR}),
    EXTERNAL_AI: frozenset({Tlp.CLEAR, Tlp.GREEN}),
}

# Keys of ExportProfilePreview.excluded_by_tlp, in display order.
MARKING_KEYS: tuple[str, ...] = (UNSPECIFIED, *(t.value for t in Tlp))

_AMBER_RANK = TLP_RANK[Tlp.AMBER]


def parse_tlp(value: str | None) -> Tlp | None:
    """Stored string → :class:`Tlp` (``None`` stays Unspecified)."""
    return None if value is None else Tlp(value)


def rank(value: Tlp | str | None) -> int | None:
    return None if value is None else TLP_RANK[Tlp(value)]


def is_downgrade(old: Tlp | str | None, new: Tlp | str | None) -> bool:
    """Whether changing a feed/report marking from *old* to *new* loosens it.

    A downgrade is a specified marking replaced by a lower rank or by
    Unspecified. Unspecified → any marking is an initial classification, not a
    downgrade (owner decision, see the contract's backend notes).
    """
    if old is None:
        return False
    if new is None:
        return True
    return TLP_RANK[Tlp(new)] < TLP_RANK[Tlp(old)]


def more_restrictive(old: Tlp | str | None, new: Tlp | str | None) -> Tlp | None:
    """The more restrictive of two markings; a specified value replaces NULL."""
    if old is None:
        return parse_tlp(new)
    if new is None:
        return parse_tlp(old)
    return Tlp(new) if TLP_RANK[Tlp(new)] > TLP_RANK[Tlp(old)] else Tlp(old)


def marking_key(value: Tlp | str | None) -> str:
    """Counter / query-parameter token: the marking value or ``"unspecified"``."""
    return UNSPECIFIED if value is None else Tlp(value).value


# ── Destination gate ─────────────────────────────────────────────────────


def is_shareable(effective: Tlp | str | None, destination: str) -> bool:
    """Whether an effective marking may leave to *destination*.

    Unknown or unsupported destinations allow nothing (fail closed).
    """
    allowed = _ALLOWED.get(str(getattr(destination, "value", destination)))
    if allowed is None:
        return False
    try:
        marking = parse_tlp(effective)
    except ValueError:
        return False  # garbage is never shareable
    return marking in allowed


def shareable_clause(effective: ColumnElement[Any], destination: str) -> ColumnElement[bool]:
    """SQL form of :func:`is_shareable` for an effective-marking expression.

    NULL-safe: ``NOT shareable_clause(...)`` selects exactly the withheld rows.
    """
    allowed = _ALLOWED.get(str(getattr(destination, "value", destination)))
    if not allowed:
        return false()
    tokens = [marking_key(m) for m in allowed]
    return func.coalesce(effective, literal(UNSPECIFIED)).in_(tokens)


def tlp_filter(column: ColumnElement[Any], tokens: Sequence[str]) -> ColumnElement[bool]:
    """Match ANY of the marking tokens (a TLP value or ``"unspecified"``)."""
    values = [t for t in tokens if t != UNSPECIFIED]
    clauses: list[ColumnElement[bool]] = []
    if values:
        clauses.append(column.in_(values))
    if UNSPECIFIED in tokens:
        clauses.append(column.is_(None))
    return or_(*clauses)


# ── Effective marking (SQL) ──────────────────────────────────────────────


def tlp_rank_expr(column: ColumnElement[Any]) -> ColumnElement[Any]:
    """Map a stored marking to its rank; NULL (Unspecified) stays NULL."""
    return case(*((column == t.value, TLP_RANK[t]) for t in Tlp), else_=None)


def _sortable_expr(column: ColumnElement[Any]) -> ColumnElement[Any]:
    """Marking prefixed with its rank digit (``'2amber'``) so MAX picks the highest.

    Unspecified maps to ``''``, which sorts below every marking.
    """
    return func.coalesce(
        case(*((column == t.value, f"{TLP_RANK[t]}{t.value}") for t in Tlp), else_=None),
        literal(""),
    )


class _Greatest(FunctionElement[str]):
    """GREATEST of non-NULL values (scalar ``max(a, b, ...)`` on SQLite)."""

    type = String()
    inherit_cache = True
    name = "tlp_greatest"


@compiles(_Greatest)
def _compile_greatest(element: _Greatest, compiler: Any, **kw: Any) -> str:
    return f"GREATEST({compiler.process(element.clauses, **kw)})"


@compiles(_Greatest, "sqlite")
def _compile_greatest_sqlite(element: _Greatest, compiler: Any, **kw: Any) -> str:
    return f"max({compiler.process(element.clauses, **kw)})"


def effective_tlp_expr() -> ColumnElement[Any]:
    """Correlated SQL expression for ``Observable``'s effective marking.

    Inputs: the ``tlp`` of every feed in its sources, of every linked report,
    and ``manual_tlp`` — the latter only if it is set or the observable has
    neither a feed nor a report. Then::

        override set                          -> override
        any input Unspecified and max < AMBER -> Unspecified (NULL)
        otherwise                             -> most restrictive input

    So adding an input can only keep or raise restriction.

    One scalar subquery joins the observable to all its feed and report
    inputs. The join may repeat rows (feeds x reports), which is harmless
    because only MAX aggregates are taken.
    """
    obs = aliased(Observable)
    src = aliased(ObservableSource)
    feed = aliased(Feed)
    link = report_observables.alias("tlp_link")
    report = aliased(Report)

    row_highest = _Greatest(
        _sortable_expr(feed.tlp),
        _sortable_expr(report.tlp),
        _sortable_expr(obs.manual_tlp),
    )
    row_unspecified = case(
        (src.id.is_not(None) & feed.tlp.is_(None), 1),
        (link.c.report_id.is_not(None) & report.tlp.is_(None), 1),
        (obs.manual_tlp.is_(None) & src.id.is_(None) & link.c.report_id.is_(None), 1),
        else_=0,
    )
    highest = func.max(row_highest)
    computed = (
        select(
            case(
                # Below AMBER means '', '0clear' or '1green' (all sort before '2').
                ((func.max(row_unspecified) == 1) & (highest < literal(str(_AMBER_RANK))), None),
                else_=func.nullif(func.substr(highest, 2), literal("")),
            )
        )
        .select_from(obs)
        .outerjoin(src, src.observable_id == obs.id)
        .outerjoin(feed, feed.id == src.feed_id)
        .outerjoin(link, link.c.observable_id == obs.id)
        .outerjoin(report, report.id == link.c.report_id)
        .where(obs.id == Observable.id)
        .correlate(Observable)
        .scalar_subquery()
    )
    return case(
        (Observable.tlp_override.is_not(None), Observable.tlp_override),
        else_=computed,
    )


async def effective_tlp_map(
    db: AsyncSession, observable_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, Tlp | None]:
    """Effective marking for each observable id (chunked)."""
    ids = list(dict.fromkeys(observable_ids))
    out: dict[uuid.UUID, Tlp | None] = {}
    effective = effective_tlp_expr()
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        rows = await db.execute(select(Observable.id, effective).where(Observable.id.in_(chunk)))
        for obs_id, value in rows.all():
            out[obs_id] = parse_tlp(value)
    return out


@dataclass(frozen=True)
class MarkingInput:
    """One input to an observable's effective marking (for display)."""

    kind: str  # "feed" | "report" | "manual"
    id: uuid.UUID | None
    name: str
    tlp: Tlp | None


@dataclass(frozen=True)
class MarkingContext:
    effective: Tlp | None
    sources: list[MarkingInput]


async def describe_markings(
    db: AsyncSession, observables: Sequence[Observable]
) -> dict[uuid.UUID, MarkingContext]:
    """Effective marking plus every input, so original restrictions stay visible.

    Expects ``Observable.sources`` (and their feeds) to be loaded.
    """
    ids = [o.id for o in observables]
    effective = await effective_tlp_map(db, ids)
    reports: dict[uuid.UUID, list[MarkingInput]] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        rows = await db.execute(
            select(report_observables.c.observable_id, Report.id, Report.title, Report.tlp)
            .join(Report, Report.id == report_observables.c.report_id)
            .where(report_observables.c.observable_id.in_(chunk))
            .order_by(Report.title, Report.id)
        )
        for obs_id, report_id, title, tlp in rows.all():
            reports.setdefault(obs_id, []).append(
                MarkingInput("report", report_id, title, parse_tlp(tlp))
            )

    out: dict[uuid.UUID, MarkingContext] = {}
    for obs in observables:
        inputs = [
            MarkingInput("feed", s.feed_id, s.feed.name, parse_tlp(s.feed.tlp))
            for s in sorted(obs.sources, key=lambda s: s.feed.name if s.feed else "")
            if s.feed is not None
        ]
        inputs.extend(reports.get(obs.id, []))
        if obs.manual_tlp is not None or not inputs:
            inputs.append(MarkingInput("manual", None, "Manual", parse_tlp(obs.manual_tlp)))
        out[obs.id] = MarkingContext(effective.get(obs.id), inputs)
    return out


# ── External AI gate ─────────────────────────────────────────────────────


async def filter_for_external_ai[T: (Observable, Report)](
    db: AsyncSession, items: Sequence[T]
) -> list[T]:
    """Keep only observables/reports whose marking may go to an external AI.

    Every future feature that sends instance data to an AI provider must pass
    its data through this first. No such feature exists today (#13 is
    configuration only).
    """
    observables = [item for item in items if isinstance(item, Observable)]
    markings = await effective_tlp_map(db, (o.id for o in observables)) if observables else {}
    kept: list[T] = []
    for item in items:
        if isinstance(item, Observable):
            marking = markings.get(item.id)
            if item.id not in markings:
                continue  # deleted meanwhile: fail closed
        elif isinstance(item, Report):
            marking = parse_tlp(item.tlp)
        else:  # pragma: no cover - typed out
            continue
        if is_shareable(marking, EXTERNAL_AI):
            kept.append(item)
    return kept


class TlpDowngradeReasonRequiredError(ValueError):
    """A feed/report marking was loosened without ``tlp_change_reason``."""


def check_marking_change(
    kind: str, entity_id: object, old: str | None, new: str | None, reason: str | None
) -> None:
    """Enforce the downgrade rule for a feed/report marking change.

    Tightening and initial classification need no reason. A downgrade without
    a reason raises; with one, it is logged at INFO.
    """
    if not is_downgrade(old, new):
        return
    if not reason:
        raise TlpDowngradeReasonRequiredError(
            f"Loosening a {kind}'s TLP marking from {marking_key(old)} to "
            f"{marking_key(new)} requires tlp_change_reason (1-500 characters)"
        )
    log_downgrade(kind, entity_id, old, new, reason)


def log_downgrade(
    kind: str, entity_id: object, old: str | None, new: str | None, reason: str
) -> None:
    """Record an authorized downgrade in the application log (no audit-log system)."""
    logger.info(
        "TLP downgrade on %s %s: %s -> %s; reason: %s",
        kind,
        entity_id,
        marking_key(old),
        marking_key(new),
        reason,
    )
