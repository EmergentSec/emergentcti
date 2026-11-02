"""The single entry point for accounted AI inference (issue #17).

Binding contract: ``docs/superpowers/specs/2026-11-02-ai-usage-guardrails.md``.

Every billable provider call goes through :func:`run_inference`, which:

1. **Admits** the request in one short transaction that locks the usage-policy
   row. On PostgreSQL that is ``SELECT … FOR UPDATE``. SQLite ignores
   ``FOR UPDATE``, so the transaction starts with a no-op ``UPDATE`` of the
   policy row: that takes SQLite's single writer lock before anything is read,
   which serializes admissions just as well. Checks run in a fixed order:
   unpriced model and policy, concurrency, requests in the last 60 seconds, then
   the monthly budget. A rejection raises :class:`GatewayRejectionError` and writes
   no usage record. Admission inserts a ``reserved`` record and commits.
2. **Dispatches** outside any database transaction, to exactly the requested
   provider and model, once. Nothing here retries or falls back.
3. **Reconciles** in a new transaction, exactly once per record: the
   ``UPDATE`` only matches while ``status = 'reserved'``. Cancellation is
   reconciled as ``cancelled``/``unknown`` in a shielded task before the
   ``CancelledError`` propagates.

If anything fails after admission but before the request is sent (the
``before_dispatch`` audit hook, decrypting the key), the reservation is deleted
through the same ``status = 'reserved'`` guard: a request that never left is
never recorded.

Usage records hold metadata only: never the prompt, the response, a provider
error body or a credential. Unknown tokens and costs stay ``NULL``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from time import perf_counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import Numeric, case, cast, delete, func, or_, select, update

from cti.core.security import decrypt_config
from cti.models.ai_usage import (
    AiAction,
    AiModelPricing,
    AiUsagePolicy,
    AiUsageRecord,
    Billable,
    CostSource,
    UnpricedModelPolicy,
    UsageSource,
    UsageStatus,
)
from cti.models.audit import ActorType
from cti.schemas.ai import AiErrorCategory
from cti.services.ai.base import (
    INFERENCE_PROMPT,
    REQUEST_TIMEOUT_SECONDS,
    AdapterUsage,
    AiAdapterError,
    make_ai_error,
)
from cti.services.ai.outbound_types import ApprovedOutbound
from cti.services.ai.registry import get_adapter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from cti.models.ai import AiProvider
    from cti.schemas.ai import AiError
    from cti.services.ai.base import AiProviderAdapter
    from cti.services.audit import Actor

    SessionContextFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
    BeforeDispatch = Callable[[], Awaitable[None]]

logger = logging.getLogger(__name__)

#: A ``reserved`` record older than this is presumed orphaned (process crash):
#: it stops counting toward concurrency but its reservation still counts as spend.
STALE_RESERVATION_AFTER = timedelta(seconds=REQUEST_TIMEOUT_SECONDS + 60)
RATE_WINDOW = timedelta(seconds=60)
#: Extra input tokens allowed for per-message framing in the reservation bound.
INPUT_TOKEN_OVERHEAD = 64
ACTIONS_IN_SCOPE: tuple[AiAction, ...] = tuple(AiAction)

_PER_MTOK = Decimal(1_000_000)
_USD_QUANTUM = Decimal("0.000001")
#: Provider responses that prove the request was refused without inference.
_NOT_BILLABLE_STATUSES = frozenset({400, 401, 403, 404})


# ── Session factory (test hook) ───────────────────────────────────────────

#: When set, the gateway opens sessions with this callable instead of
#: :data:`cti.core.database.async_session_factory` (see ``tests/conftest.py``).
_session_factory: SessionContextFactory | None = None


def independent_session() -> AbstractAsyncContextManager[AsyncSession]:
    """A new session, independent of the request's. The default ``db_factory``."""
    if _session_factory is not None:
        return _session_factory()
    from cti.core import database  # Late import: keeps engine creation lazy.

    return database.async_session_factory()


def _now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; every stored timestamp is UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# ── Errors and results ─────────────────────────────────────────────────────


class GatewayRejectionError(Exception):
    """Refused before dispatch. Nothing was sent and no usage record exists."""

    def __init__(self, status_code: int, category: AiErrorCategory) -> None:
        super().__init__(category.value)
        self.status_code = status_code
        self.error = make_ai_error(category)


@dataclass(frozen=True, slots=True)
class Pricing:
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal


@dataclass(frozen=True, slots=True)
class InferenceOutcome:
    """The result of one gateway call. ``record_id`` is None only when nothing
    was sent (the reservation was released before dispatch)."""

    ok: bool
    error: AiError | None
    latency_ms: int | None
    record_id: uuid.UUID | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_source: UsageSource = UsageSource.UNKNOWN
    cost_usd: Decimal | None = None
    cost_source: CostSource = CostSource.UNKNOWN


@dataclass(frozen=True, slots=True)
class _Admitted:
    record_id: uuid.UUID
    credentials_encrypted: bytes
    max_output_tokens: int
    pricing: Pricing | None


# ── Money ──────────────────────────────────────────────────────────────────


def _usd(value: Decimal, rounding: str = ROUND_HALF_UP) -> Decimal:
    return value.quantize(_USD_QUANTUM, rounding=rounding)


def format_usd(value: Decimal | None) -> str | None:
    return None if value is None else str(_usd(Decimal(value)))


def input_token_upper_bound(prompt: str) -> int:
    """Every BPE token covers at least one byte, so bytes + framing bounds input."""
    return len(prompt.encode("utf-8")) + INPUT_TOKEN_OVERHEAD


def reservation_upper_bound(
    prompt: str, max_output_tokens: int, pricing: Pricing | None
) -> Decimal | None:
    """The most this request can cost, or None when the model is unpriced.

    Rounded up, so the reservation never understates the bound.
    """
    if pricing is None:
        return None
    total = (
        Decimal(input_token_upper_bound(prompt)) * pricing.input_usd_per_mtok
        + Decimal(max_output_tokens) * pricing.output_usd_per_mtok
    ) / _PER_MTOK
    return _usd(total, ROUND_CEILING)


def estimate_cost(
    input_tokens: int | None, output_tokens: int | None, pricing: Pricing | None
) -> Decimal | None:
    """A local estimate, only when both counts are known and the model is priced."""
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    total = (
        Decimal(input_tokens) * pricing.input_usd_per_mtok
        + Decimal(output_tokens) * pricing.output_usd_per_mtok
    ) / _PER_MTOK
    return _usd(total)


def committed_amount() -> ColumnElement[Any]:
    """SQL: each record's single contribution to committed spend (see the contract)."""
    return case(
        (AiUsageRecord.cost_usd.is_not(None), AiUsageRecord.cost_usd),
        (
            or_(
                AiUsageRecord.status == UsageStatus.RESERVED.value,
                AiUsageRecord.billable.in_([Billable.YES.value, Billable.UNKNOWN.value]),
            ),
            func.coalesce(AiUsageRecord.reserved_usd, 0),
        ),
        else_=0,
    )


def committed_contribution(
    *, status: str, billable: str, reserved_usd: Decimal | None, cost_usd: Decimal | None
) -> Decimal:
    """Python mirror of :func:`committed_amount`, used by the usage report."""
    if cost_usd is not None:
        return Decimal(cost_usd)
    if status == UsageStatus.RESERVED.value or billable in (
        Billable.YES.value,
        Billable.UNKNOWN.value,
    ):
        return Decimal(reserved_usd) if reserved_usd is not None else Decimal(0)
    return Decimal(0)


# ── Periods ────────────────────────────────────────────────────────────────


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """``[YYYY-MM-01T00:00Z, next month)``: the accounting period, in UTC."""
    start = datetime(year, month, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    return start, end


def current_month(now: datetime | None = None) -> tuple[int, int]:
    moment = as_utc(now or _now())
    return moment.year, moment.month


async def committed_spend(db: AsyncSession, start: datetime, end: datetime) -> Decimal:
    total = await db.scalar(
        select(func.coalesce(func.sum(cast(committed_amount(), Numeric(14, 6))), 0)).where(
            AiUsageRecord.started_at >= start, AiUsageRecord.started_at < end
        )
    )
    return _usd(Decimal(str(total or 0)))


# ── Policy and pricing reads ───────────────────────────────────────────────


def default_policy() -> AiUsagePolicy:
    # Column defaults only apply on INSERT; set them for an unsaved instance too.
    return AiUsagePolicy(
        id=1,
        monthly_budget_usd=None,
        max_output_tokens=1024,
        max_concurrent_requests=2,
        max_requests_per_minute=10,
        unpriced_model_policy=UnpricedModelPolicy.BLOCK.value,
    )


async def read_policy(db: AsyncSession) -> AiUsagePolicy:
    """The policy without locking (defaults if migration 011's row is absent)."""
    policy = await db.get(AiUsagePolicy, 1)
    return policy if policy is not None else default_policy()


async def _locked_policy(db: AsyncSession) -> AiUsagePolicy:
    if db.get_bind().dialect.name == "sqlite":
        # Take SQLite's writer lock before reading anything (see module docstring).
        await db.execute(update(AiUsagePolicy).where(AiUsagePolicy.id == 1).values(id=1))
    policy = await db.scalar(select(AiUsagePolicy).where(AiUsagePolicy.id == 1).with_for_update())
    if policy is None:  # Only without migration 011 (test schemas): create it.
        policy = default_policy()
        db.add(policy)
        await db.flush()
    return policy


async def read_pricing(db: AsyncSession, provider: AiProvider, model: str) -> Pricing | None:
    row = await db.get(AiModelPricing, (provider.value, model))
    if row is None:
        return None
    return Pricing(
        input_usd_per_mtok=Decimal(row.input_usd_per_mtok),
        output_usd_per_mtok=Decimal(row.output_usd_per_mtok),
    )


# ── Content approval ───────────────────────────────────────────────────────


def require_approval(
    action: AiAction,
    provider: AiProvider,
    model: str,
    prompt: str,
    approved: ApprovedOutbound | None,
) -> None:
    """``inference_test`` sends only the fixed prompt; anything else needs an
    :class:`ApprovedOutbound` for exactly this provider, model and content."""
    if action == AiAction.INFERENCE_TEST:
        if prompt != INFERENCE_PROMPT:
            raise GatewayRejectionError(403, AiErrorCategory.SHARING_NOT_APPROVED)
        return
    if (
        not isinstance(approved, ApprovedOutbound)
        or approved.provider != provider
        or approved.model != model
        or approved.content != prompt
    ):
        raise GatewayRejectionError(403, AiErrorCategory.SHARING_NOT_APPROVED)


# ── Admission, release, reconcile ──────────────────────────────────────────


def _actor_user_id(actor: Actor) -> uuid.UUID | None:
    if actor.type != ActorType.USER or actor.id is None:
        return None
    try:
        return uuid.UUID(actor.id)
    except ValueError:
        return None


async def _count(db: AsyncSession, *conditions: ColumnElement[bool]) -> int:
    return int(await db.scalar(select(func.count()).where(*conditions)) or 0)


async def _admit(
    db_factory: SessionContextFactory,
    *,
    actor: Actor,
    action: AiAction,
    provider: AiProvider,
    model: str,
    prompt: str,
    retry_of: uuid.UUID | None,
) -> _Admitted:
    from cti.models.ai import AiProviderConfig  # Avoid a models → services cycle.

    async with db_factory() as db:
        try:
            policy = await _locked_policy(db)
            config = await db.get(AiProviderConfig, provider)
            if config is None:
                raise GatewayRejectionError(409, AiErrorCategory.NOT_CONFIGURED)
            pricing = await read_pricing(db, provider, model)
            if pricing is None and policy.unpriced_model_policy != UnpricedModelPolicy.PERMIT:
                raise GatewayRejectionError(409, AiErrorCategory.MODEL_BLOCKED_UNPRICED)

            now = _now()
            active = await _count(
                db,
                AiUsageRecord.status == UsageStatus.RESERVED.value,
                AiUsageRecord.started_at > now - STALE_RESERVATION_AFTER,
            )
            if active >= policy.max_concurrent_requests:
                raise GatewayRejectionError(429, AiErrorCategory.CONCURRENCY_LIMIT)
            recent = await _count(db, AiUsageRecord.started_at > now - RATE_WINDOW)
            if recent >= policy.max_requests_per_minute:
                raise GatewayRejectionError(429, AiErrorCategory.LOCAL_RATE_LIMITED)

            reserved = reservation_upper_bound(prompt, policy.max_output_tokens, pricing)
            if policy.monthly_budget_usd is not None:
                start, end = month_bounds(*current_month(now))
                committed = await committed_spend(db, start, end)
                if committed + (reserved or Decimal(0)) > Decimal(policy.monthly_budget_usd):
                    raise GatewayRejectionError(402, AiErrorCategory.BUDGET_EXCEEDED)

            record = AiUsageRecord(
                id=uuid.uuid4(),
                actor_user_id=_actor_user_id(actor),
                actor_label=None if actor.label is None else str(actor.label)[:255],
                action=action.value,
                provider=provider.value,
                model=model,
                status=UsageStatus.RESERVED.value,
                billable=Billable.UNKNOWN.value,
                started_at=now,
                usage_source=UsageSource.UNKNOWN.value,
                reserved_usd=reserved,
                cost_source=CostSource.UNKNOWN.value,
                retry_of=retry_of,
            )
            db.add(record)
            admitted = _Admitted(
                record_id=record.id,
                credentials_encrypted=config.credentials_encrypted,
                max_output_tokens=policy.max_output_tokens,
                pricing=pricing,
            )
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
    return admitted


async def _release(db_factory: SessionContextFactory, record_id: uuid.UUID) -> None:
    """Delete a reservation that was never dispatched (guarded on ``reserved``)."""
    async with db_factory() as db:
        await db.execute(
            delete(AiUsageRecord).where(
                AiUsageRecord.id == record_id,
                AiUsageRecord.status == UsageStatus.RESERVED.value,
            )
        )
        await db.commit()


async def reconcile(
    db_factory: SessionContextFactory,
    record_id: uuid.UUID,
    *,
    status: UsageStatus,
    billable: Billable,
    usage: AdapterUsage | None,
    pricing: Pricing | None,
    latency_ms: int | None,
    error_category: AiErrorCategory | None,
) -> bool:
    """Settle a reservation. Returns False (and changes nothing) if it was
    already settled: a record is reconciled exactly once."""
    input_tokens = usage.input_tokens if usage is not None else None
    output_tokens = usage.output_tokens if usage is not None else None
    reported = input_tokens is not None or output_tokens is not None
    cost = estimate_cost(input_tokens, output_tokens, pricing)
    async with db_factory() as db:
        result = await db.execute(
            update(AiUsageRecord)
            .where(
                AiUsageRecord.id == record_id,
                AiUsageRecord.status == UsageStatus.RESERVED.value,
            )
            .values(
                status=status.value,
                billable=billable.value,
                completed_at=_now(),
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                usage_source=(
                    UsageSource.PROVIDER_REPORTED.value if reported else UsageSource.UNKNOWN.value
                ),
                cost_usd=cost,
                cost_source=(
                    CostSource.ESTIMATED.value if cost is not None else CostSource.UNKNOWN.value
                ),
                error_category=error_category.value if error_category is not None else None,
            )
            .execution_options(synchronize_session=False)
        )
        await db.commit()
    settled = getattr(result, "rowcount", 0) == 1
    if not settled:
        logger.warning("AI usage record %s was already reconciled; ignored", record_id)
    return settled


def billable_for_error(exc: AiAdapterError) -> Billable:
    """``no`` only when the provider provably did no work; otherwise ``unknown``.

    Timeouts, network errors after send, 429 and 5xx may have been billed.
    """
    if not exc.sent or exc.status_code in _NOT_BILLABLE_STATUSES:
        return Billable.NO
    return Billable.UNKNOWN


# Strong references to reconcile/release tasks that outlive a cancelled caller.
_pending: set[asyncio.Task[Any]] = set()


async def _shielded(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run ``coro`` to completion even if the caller is cancelled meanwhile."""
    task = asyncio.ensure_future(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)
    return await asyncio.shield(task)


async def _shielded_quietly(coro: Coroutine[Any, Any, Any]) -> None:
    """Like :func:`_shielded` on a path that is already raising: log, never mask."""
    try:
        await _shielded(coro)
    except asyncio.CancelledError:
        pass  # The task keeps running; the original exception propagates.
    except Exception as exc:
        logger.error("AI usage bookkeeping failed: %s", type(exc).__name__)


def _decrypt_api_key(credentials_encrypted: bytes) -> str:
    try:
        payload = decrypt_config(credentials_encrypted)
        api_key = payload["api_key"]
    except Exception:  # the encrypted payload must never escape through the error
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR), sent=False) from None
    if not isinstance(api_key, str) or not api_key:
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR), sent=False)
    return api_key


# ── Entry point ────────────────────────────────────────────────────────────


async def run_inference(
    db_factory: SessionContextFactory,
    *,
    actor: Actor,
    action: AiAction,
    provider: AiProvider,
    model: str,
    prompt: str,
    approved: ApprovedOutbound | None,
    retry_of: uuid.UUID | None,
    adapter: AiProviderAdapter | None = None,
    before_dispatch: BeforeDispatch | None = None,
) -> InferenceOutcome:
    """Admit, dispatch once, reconcile once. See the module docstring.

    ``adapter`` defaults to the registry's adapter for ``provider``.
    ``before_dispatch`` is awaited after admission and immediately before the
    provider is contacted (routes write the ``ai.request`` initiated audit
    event there); if it raises, the reservation is released and nothing is sent.

    Raises :class:`GatewayRejectionError` when refused before dispatch.
    """
    require_approval(action, provider, model, prompt, approved)
    provider_adapter = adapter if adapter is not None else get_adapter(provider)
    admitted = await _admit(
        db_factory,
        actor=actor,
        action=action,
        provider=provider,
        model=model,
        prompt=prompt,
        retry_of=retry_of,
    )
    record_id = admitted.record_id

    # Not yet sent: any failure here releases the reservation.
    try:
        if before_dispatch is not None:
            await before_dispatch()
        api_key = _decrypt_api_key(admitted.credentials_encrypted)
    except AiAdapterError as exc:
        await _shielded(_release(db_factory, record_id))
        return InferenceOutcome(ok=False, error=exc.error, latency_ms=None, record_id=None)
    except BaseException:
        await _shielded_quietly(_release(db_factory, record_id))
        raise

    def settle(
        status: UsageStatus,
        billable: Billable,
        usage: AdapterUsage | None,
        latency_ms: int | None,
        error_category: AiErrorCategory | None,
    ) -> Coroutine[Any, Any, bool]:
        return reconcile(
            db_factory,
            record_id,
            status=status,
            billable=billable,
            usage=usage,
            pricing=admitted.pricing,
            latency_ms=latency_ms,
            error_category=error_category,
        )

    started = perf_counter()
    try:
        if action == AiAction.INFERENCE_TEST:
            raw_usage = await provider_adapter.inference_test(
                api_key, model, max_output_tokens=admitted.max_output_tokens
            )
        else:
            raw_usage = await provider_adapter.complete(
                api_key, model, prompt, admitted.max_output_tokens
            )
    except AiAdapterError as exc:
        latency_ms = round((perf_counter() - started) * 1000)
        await _shielded(
            settle(
                UsageStatus.FAILED, billable_for_error(exc), None, latency_ms, exc.error.category
            )
        )
        return InferenceOutcome(ok=False, error=exc.error, latency_ms=None, record_id=record_id)
    except asyncio.CancelledError:
        await _shielded_quietly(settle(UsageStatus.CANCELLED, Billable.UNKNOWN, None, None, None))
        raise
    except BaseException:
        await _shielded_quietly(
            settle(UsageStatus.FAILED, Billable.UNKNOWN, None, None, AiErrorCategory.PROVIDER_ERROR)
        )
        raise

    latency_ms = round((perf_counter() - started) * 1000)
    usage = raw_usage if isinstance(raw_usage, AdapterUsage) else AdapterUsage(None, None)
    await _shielded(settle(UsageStatus.SUCCEEDED, Billable.YES, usage, latency_ms, None))
    cost = estimate_cost(usage.input_tokens, usage.output_tokens, admitted.pricing)
    reported = usage.input_tokens is not None or usage.output_tokens is not None
    return InferenceOutcome(
        ok=True,
        error=None,
        latency_ms=latency_ms,
        record_id=record_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        usage_source=UsageSource.PROVIDER_REPORTED if reported else UsageSource.UNKNOWN,
        cost_usd=cost,
        cost_source=CostSource.ESTIMATED if cost is not None else CostSource.UNKNOWN,
    )
