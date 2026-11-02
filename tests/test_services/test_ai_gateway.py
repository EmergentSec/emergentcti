"""AI usage gateway: admission, accounting and reconciliation (#17).

Provider HTTP is mocked with pytest-httpx or replaced by an in-process fake
adapter; nothing leaves the process.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from cti.core.security import encrypt_config
from cti.models.ai import AiProvider, AiProviderConfig
from cti.models.ai_usage import AiAction, AiModelPricing, AiUsagePolicy, AiUsageRecord
from cti.models.audit import ActorType
from cti.schemas.ai import AiErrorCategory
from cti.services.ai import gateway
from cti.services.ai.base import INFERENCE_PROMPT, AdapterUsage, AiAdapterError
from cti.services.ai.outbound_types import ApprovedOutbound, OutboundRef
from cti.services.audit import Actor

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock
    from sqlalchemy.ext.asyncio import AsyncSession

FAKE_KEY = "sk-test-gateway-not-a-real-key-7777"
SENTINEL = "RESPONSE-SENTINEL-feedface"
CHAT_URL = "https://api.openai.com/v1/chat/completions"
ACTOR = Actor(ActorType.USER, None, "analyst-one")
# 30-byte prompt + 64 overhead = 94 input tokens; 1024 output tokens.
# At $1000/Mtok in and out the reservation is (94 + 1024) * 1000 / 1e6.
EXPENSIVE = Decimal("1000")
EXPENSIVE_RESERVATION = Decimal("1.118000")
NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)


# ── fixtures and helpers ───────────────────────────────────────────────────


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[datetime]:
    """The gateway's clock: set ``clock[0]`` to move time."""
    moment = [NOW]
    monkeypatch.setattr(gateway, "_now", lambda: moment[0])
    return moment


@pytest.fixture
async def configured(db_session: AsyncSession) -> None:
    db_session.add(
        AiProviderConfig(
            provider=AiProvider.OPENAI,
            credentials_encrypted=encrypt_config({"api_key": FAKE_KEY}),
        )
    )
    await db_session.commit()


async def set_policy(db: AsyncSession, **values: Any) -> None:
    policy = await db.get(AiUsagePolicy, 1)
    if policy is None:
        policy = gateway.default_policy()
        db.add(policy)
    for name, value in values.items():
        setattr(policy, name, value)
    await db.commit()


async def set_price(
    db: AsyncSession,
    model: str = "gpt-test",
    input_price: Decimal = Decimal("1"),
    output_price: Decimal = Decimal("2"),
) -> None:
    db.add(
        AiModelPricing(
            provider="openai",
            model=model,
            input_usd_per_mtok=input_price,
            output_usd_per_mtok=output_price,
        )
    )
    await db.commit()


async def records(db: AsyncSession) -> list[Any]:
    """Rows straight from the table, bypassing the identity map."""
    result = await db.execute(
        select(AiUsageRecord.__table__).order_by(AiUsageRecord.started_at, AiUsageRecord.id)
    )
    return list(result.all())


async def add_record(db: AsyncSession, **values: Any) -> AiUsageRecord:
    row: dict[str, Any] = {
        "action": "inference_test",
        "provider": "openai",
        "model": "gpt-test",
        "status": "succeeded",
        "billable": "yes",
        "started_at": NOW,
        "usage_source": "unknown",
        "cost_source": "unknown",
    }
    row.update(values)
    record = AiUsageRecord(**row)
    db.add(record)
    await db.commit()
    return record


async def run(**overrides: Any) -> gateway.InferenceOutcome:
    kwargs: dict[str, Any] = {
        "actor": ACTOR,
        "action": AiAction.INFERENCE_TEST,
        "provider": AiProvider.OPENAI,
        "model": "gpt-test",
        "prompt": INFERENCE_PROMPT,
        "approved": None,
        "retry_of": None,
    }
    kwargs.update(overrides)
    return await gateway.run_inference(gateway.independent_session, **kwargs)


def ok_response(httpx_mock: HTTPXMock, usage: object = None) -> None:
    body: dict[str, Any] = {"choices": [{"message": {"content": SENTINEL}}]}
    if usage is not None:
        body["usage"] = usage
    httpx_mock.add_response(url=CHAT_URL, json=body)


async def committed(db: AsyncSession, month: tuple[int, int] = (2026, 11)) -> Decimal:
    return await gateway.committed_spend(db, *gateway.month_bounds(*month))


class BlockingAdapter:
    """Holds every inference open until released, so requests stay in flight."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.entered = asyncio.Event()
        self.calls = 0

    async def inference_test(self, api_key: str, model: str, **_: object) -> AdapterUsage:
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return AdapterUsage(input_tokens=3, output_tokens=1)


# ── accounting per outcome ─────────────────────────────────────────────────


async def test_success_records_provider_usage_and_estimated_cost(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    ok_response(httpx_mock, {"prompt_tokens": 12, "completion_tokens": 7})

    outcome = await run()

    assert outcome.ok is True
    assert (outcome.input_tokens, outcome.output_tokens) == (12, 7)
    # (12 * $1 + 7 * $2) / 1e6
    assert outcome.cost_usd == Decimal("0.000026")
    [row] = await records(db_session)
    assert row.id == outcome.record_id
    assert (row.status, row.billable, row.usage_source, row.cost_source) == (
        "succeeded",
        "yes",
        "provider_reported",
        "estimated",
    )
    assert (row.input_tokens, row.output_tokens) == (12, 7)
    assert row.reserved_usd == Decimal("0.002142")  # (94 * 1 + 1024 * 2) / 1e6
    assert row.cost_usd == Decimal("0.000026")
    assert row.completed_at is not None and row.latency_ms is not None
    assert row.actor_label == "analyst-one"
    # Committed spend uses the known cost, not the reservation: no double count.
    assert await committed(db_session) == Decimal("0.000026")
    # The policy's max_output_tokens is the provider's max_tokens.
    sent = json.loads(httpx_mock.get_request().content)  # type: ignore[union-attr]
    assert sent["max_tokens"] == 1024


async def test_success_without_usage_keeps_tokens_and_cost_unknown(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    ok_response(httpx_mock)

    outcome = await run()

    assert outcome.ok is True
    assert outcome.input_tokens is None and outcome.cost_usd is None
    [row] = await records(db_session)
    assert (row.status, row.billable) == ("succeeded", "yes")
    assert row.input_tokens is None and row.output_tokens is None
    assert row.cost_usd is None
    assert (row.usage_source, row.cost_source) == ("unknown", "unknown")
    # Billed but cost unknown: the reservation stays committed.
    assert await committed(db_session) == Decimal("0.002142")


@pytest.mark.parametrize(
    ("status_code", "category", "billable"),
    [
        (400, AiErrorCategory.PROVIDER_ERROR, "no"),
        (401, AiErrorCategory.INVALID_CREDENTIALS, "no"),
        (403, AiErrorCategory.PERMISSION_DENIED, "no"),
        (404, AiErrorCategory.MODEL_UNAVAILABLE, "no"),
        (429, AiErrorCategory.RATE_LIMITED, "unknown"),
        (500, AiErrorCategory.PROVIDER_ERROR, "unknown"),
        (503, AiErrorCategory.PROVIDER_ERROR, "unknown"),
    ],
)
async def test_provider_errors_are_failed_with_contract_billability(
    db_session: AsyncSession,
    configured: None,
    clock: list[datetime],
    httpx_mock: HTTPXMock,
    status_code: int,
    category: AiErrorCategory,
    billable: str,
) -> None:
    await set_price(db_session)
    httpx_mock.add_response(url=CHAT_URL, status_code=status_code, text=SENTINEL)

    outcome = await run()

    assert outcome.ok is False
    assert outcome.error is not None and outcome.error.category == category
    [row] = await records(db_session)
    assert (row.status, row.billable, row.error_category) == ("failed", billable, category.value)
    assert row.input_tokens is None and row.cost_usd is None
    expected = Decimal(0) if billable == "no" else Decimal("0.002142")
    assert await committed(db_session) == expected


async def test_timeout_after_send_is_failed_and_possibly_billable(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=CHAT_URL)

    outcome = await run()

    assert outcome.error is not None and outcome.error.category == AiErrorCategory.TIMEOUT
    [row] = await records(db_session)
    assert (row.status, row.billable, row.error_category) == ("failed", "unknown", "timeout")
    assert await committed(db_session) == Decimal("0.002142")


async def test_connection_refused_is_failed_and_not_billable(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    httpx_mock.add_exception(httpx.ConnectError("refused"), url=CHAT_URL)

    outcome = await run()

    assert outcome.error is not None and outcome.error.category == AiErrorCategory.NETWORK_ERROR
    [row] = await records(db_session)
    assert (row.status, row.billable) == ("failed", "no")
    assert await committed(db_session) == Decimal(0)


async def test_cancellation_after_dispatch_is_reconciled_then_reraised(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    await set_price(db_session)
    adapter = BlockingAdapter()
    task = asyncio.create_task(run(adapter=adapter))
    await asyncio.wait_for(adapter.entered.wait(), 5)
    [row] = await records(db_session)
    assert row.status == "reserved"

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    [row] = await records(db_session)
    assert (row.status, row.billable) == ("cancelled", "unknown")
    assert row.input_tokens is None and row.cost_usd is None
    assert row.completed_at is not None
    assert await committed(db_session) == Decimal("0.002142")


async def test_unexpected_adapter_exception_is_reconciled_and_propagates(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    await set_price(db_session)

    class Exploding:
        async def inference_test(self, *_: object, **__: object) -> AdapterUsage:
            raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        await run(adapter=Exploding())
    [row] = await records(db_session)
    assert (row.status, row.billable, row.error_category) == ("failed", "unknown", "provider_error")


async def test_committed_spend_counts_each_record_exactly_once(
    db_session: AsyncSession,
) -> None:
    """Every status/billable combination contributes one number; SQL == Python."""
    await add_record(
        db_session,
        status="succeeded",
        billable="yes",
        cost_usd=Decimal("0.1"),
        reserved_usd=Decimal("5"),
    )
    await add_record(db_session, status="succeeded", billable="yes", reserved_usd=Decimal("0.2"))
    await add_record(db_session, status="failed", billable="unknown", reserved_usd=Decimal("0.3"))
    await add_record(db_session, status="failed", billable="no", reserved_usd=Decimal("7"))
    await add_record(db_session, status="cancelled", billable="unknown", reserved_usd=None)
    await add_record(db_session, status="reserved", billable="unknown", reserved_usd=Decimal("0.4"))

    python_total = sum(
        (
            gateway.committed_contribution(
                status=r.status,
                billable=r.billable,
                reserved_usd=r.reserved_usd,
                cost_usd=r.cost_usd,
            )
            for r in await records(db_session)
        ),
        Decimal(0),
    )
    assert python_total == Decimal("1.0")
    assert await committed(db_session) == Decimal("1.000000")


# ── reconcile once ─────────────────────────────────────────────────────────


async def test_reconcile_applies_exactly_once(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    record = await add_record(
        db_session, status="reserved", billable="unknown", reserved_usd=Decimal("0.5")
    )
    pricing = gateway.Pricing(Decimal("1"), Decimal("1"))

    first = await gateway.reconcile(
        gateway.independent_session,
        record.id,
        status=gateway.UsageStatus.SUCCEEDED,
        billable=gateway.Billable.YES,
        usage=AdapterUsage(10, 10),
        pricing=pricing,
        latency_ms=5,
        error_category=None,
    )
    second = await gateway.reconcile(
        gateway.independent_session,
        record.id,
        status=gateway.UsageStatus.CANCELLED,
        billable=gateway.Billable.UNKNOWN,
        usage=None,
        pricing=pricing,
        latency_ms=None,
        error_category=None,
    )

    assert (first, second) == (True, False)
    [row] = await records(db_session)
    assert (row.status, row.input_tokens, row.cost_usd) == ("succeeded", 10, Decimal("0.00002"))


# ── unpriced models ────────────────────────────────────────────────────────


async def test_unpriced_model_is_blocked_by_default_before_dispatch(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()

    assert caught.value.status_code == 409
    assert caught.value.error.category == AiErrorCategory.MODEL_BLOCKED_UNPRICED
    assert httpx_mock.get_requests() == []
    assert await records(db_session) == []


async def test_unpriced_model_permitted_has_null_reservation_and_unknown_cost(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_policy(db_session, unpriced_model_policy="permit")
    ok_response(httpx_mock, {"prompt_tokens": 5, "completion_tokens": 1})

    outcome = await run()

    assert outcome.ok is True
    [row] = await records(db_session)
    assert row.reserved_usd is None
    assert (row.input_tokens, row.output_tokens) == (5, 1)
    assert row.cost_usd is None and row.cost_source == "unknown"
    assert row.usage_source == "provider_reported"
    assert await committed(db_session) == Decimal(0)


# ── budget ─────────────────────────────────────────────────────────────────


async def test_budget_exceeded_is_rejected_before_any_provider_call(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session, input_price=EXPENSIVE, output_price=EXPENSIVE)
    await set_policy(db_session, monthly_budget_usd=Decimal("1.5"))
    await add_record(db_session, cost_usd=Decimal("0.5"), started_at=NOW - timedelta(days=1))

    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()

    assert caught.value.status_code == 402
    assert caught.value.error.category == AiErrorCategory.BUDGET_EXCEEDED
    assert httpx_mock.get_requests() == []
    assert len(await records(db_session)) == 1  # only the seeded record


async def test_budget_admits_when_reservation_fits(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session, input_price=EXPENSIVE, output_price=EXPENSIVE)
    await set_policy(db_session, monthly_budget_usd=Decimal("1.118"))
    ok_response(httpx_mock, {"prompt_tokens": 1, "completion_tokens": 1})

    outcome = await run()  # 0 + 1.118 is not > 1.118

    assert outcome.ok is True


async def test_utc_month_boundary_for_budget_and_period(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session, input_price=EXPENSIVE, output_price=EXPENSIVE)
    await set_policy(db_session, monthly_budget_usd=Decimal("2"))
    last_second = datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)
    first_second = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
    await add_record(db_session, cost_usd=Decimal("1"), started_at=last_second)

    assert await committed(db_session, (2026, 11)) == Decimal("1.000000")
    assert await committed(db_session, (2026, 12)) == Decimal(0)

    # Still November: 1 + 1.118 > 2.
    clock[0] = last_second
    with pytest.raises(gateway.GatewayRejectionError):
        await run()

    # December starts at 00:00 UTC: the November record no longer counts.
    clock[0] = first_second
    ok_response(httpx_mock, {"prompt_tokens": 1, "completion_tokens": 1})
    outcome = await run()
    assert outcome.ok is True
    december = [r for r in await records(db_session) if r.id == outcome.record_id]
    assert gateway.as_utc(december[0].started_at) == first_second


async def test_month_bounds_are_utc_calendar_months() -> None:
    assert gateway.month_bounds(2026, 11) == (
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 12, 1, tzinfo=UTC),
    )
    assert gateway.month_bounds(2026, 12) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )


# ── concurrency and rate ───────────────────────────────────────────────────


async def test_concurrency_limit_counts_in_flight_requests(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    await set_price(db_session)
    await set_policy(db_session, max_concurrent_requests=2, max_requests_per_minute=100)
    first, second = BlockingAdapter(), BlockingAdapter()
    task_one = asyncio.create_task(run(adapter=first))
    await asyncio.wait_for(first.entered.wait(), 5)
    task_two = asyncio.create_task(run(adapter=second))
    await asyncio.wait_for(second.entered.wait(), 5)

    third = BlockingAdapter()
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run(adapter=third)
    assert caught.value.status_code == 429
    assert caught.value.error.category == AiErrorCategory.CONCURRENCY_LIMIT
    assert third.calls == 0

    # One at a time: the tests share one SQLite connection (see conftest), so
    # two reconciles must not interleave. PostgreSQL concurrency is covered by
    # tests/test_postgres_ai_usage.py.
    first.release.set()
    assert (await task_one).ok
    second.release.set()
    assert (await task_two).ok
    # Once settled, a new request is admitted again.
    third.release.set()
    assert (await run(adapter=third)).ok
    assert [r.status for r in await records(db_session)] == ["succeeded"] * 3


async def test_per_minute_rate_counts_every_record_including_failures(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    await set_price(db_session)
    await set_policy(db_session, max_requests_per_minute=3, max_concurrent_requests=50)
    await add_record(
        db_session, status="failed", billable="no", started_at=NOW - timedelta(seconds=61)
    )
    for seconds in (50, 30, 1):
        await add_record(
            db_session, status="failed", billable="no", started_at=NOW - timedelta(seconds=seconds)
        )

    blocked = BlockingAdapter()
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run(adapter=blocked)
    assert caught.value.error.category == AiErrorCategory.LOCAL_RATE_LIMITED
    assert caught.value.status_code == 429
    assert blocked.calls == 0

    # 11 seconds later the record from 50 seconds ago has left the window.
    clock[0] = NOW + timedelta(seconds=11)
    allowed = BlockingAdapter()
    allowed.release.set()
    assert (await run(adapter=allowed)).ok


async def test_checks_run_in_contract_order(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    """Unpriced beats concurrency, which beats rate, which beats budget."""
    await set_policy(
        db_session, max_concurrent_requests=1, max_requests_per_minute=1, monthly_budget_usd=0
    )
    await add_record(db_session, status="reserved", billable="unknown", reserved_usd=Decimal(1))

    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.MODEL_BLOCKED_UNPRICED

    await set_price(db_session)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.CONCURRENCY_LIMIT

    await set_policy(db_session, max_concurrent_requests=5)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.LOCAL_RATE_LIMITED

    await set_policy(db_session, max_requests_per_minute=5)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.BUDGET_EXCEEDED


async def test_stale_reservation_frees_concurrency_but_still_counts_as_spend(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session, input_price=EXPENSIVE, output_price=EXPENSIVE)
    await set_policy(db_session, max_concurrent_requests=1, monthly_budget_usd=Decimal("2"))
    orphan_started = NOW - gateway.STALE_RESERVATION_AFTER - timedelta(seconds=1)
    await add_record(
        db_session,
        status="reserved",
        billable="unknown",
        reserved_usd=Decimal("0.9"),
        started_at=orphan_started,
    )
    assert await committed(db_session) == Decimal("0.900000")

    # Concurrency 1 is not taken by the stale reservation, but its 0.9 plus
    # this request's 1.118 exceeds the budget of 2.
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.BUDGET_EXCEEDED

    await set_policy(db_session, monthly_budget_usd=Decimal("3"))
    ok_response(httpx_mock, {"prompt_tokens": 1, "completion_tokens": 1})
    assert (await run()).ok


async def test_fresh_reservation_still_holds_concurrency(
    db_session: AsyncSession, configured: None, clock: list[datetime]
) -> None:
    await set_price(db_session)
    await set_policy(db_session, max_concurrent_requests=1)
    await add_record(
        db_session,
        status="reserved",
        billable="unknown",
        started_at=NOW - gateway.STALE_RESERVATION_AFTER + timedelta(seconds=1),
    )
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.error.category == AiErrorCategory.CONCURRENCY_LIMIT


# ── pre-dispatch failures release the reservation ──────────────────────────


async def test_before_dispatch_failure_releases_reservation_and_sends_nothing(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)

    async def audit_down() -> None:
        assert len(await records(db_session)) == 1  # reserved while the hook runs
        raise HTTPException(status_code=503, detail="Audit log unavailable")

    with pytest.raises(HTTPException):
        await run(before_dispatch=audit_down)

    assert httpx_mock.get_requests() == []
    assert await records(db_session) == []


async def test_undecryptable_key_releases_reservation(
    db_session: AsyncSession, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    db_session.add(
        AiProviderConfig(provider=AiProvider.OPENAI, credentials_encrypted=b"not-a-token")
    )
    await db_session.commit()
    await set_price(db_session)

    outcome = await run()

    assert outcome.ok is False and outcome.record_id is None
    assert outcome.error is not None and outcome.error.category == AiErrorCategory.PROVIDER_ERROR
    assert httpx_mock.get_requests() == []
    assert await records(db_session) == []


async def test_not_configured_is_rejected_without_record(
    db_session: AsyncSession, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run()
    assert caught.value.status_code == 409
    assert caught.value.error.category == AiErrorCategory.NOT_CONFIGURED
    assert await records(db_session) == []


# ── content approval ───────────────────────────────────────────────────────

REPORT_GENERATION = cast("AiAction", "report_generation")  # stand-in: not exposed yet


def approval(**overrides: Any) -> ApprovedOutbound:
    values: dict[str, Any] = {
        "provider": AiProvider.OPENAI,
        "model": "gpt-test",
        "digest": "d" * 64,
        "content": "approved content",
        "item_refs": (OutboundRef(type="report", id="r1"),),
    }
    values.update(overrides)
    return ApprovedOutbound(**values)


@pytest.mark.parametrize(
    "approved",
    [
        None,
        approval(provider=AiProvider.ANTHROPIC),
        approval(model="gpt-other"),
        approval(content="something else"),
    ],
    ids=["missing", "other-provider", "other-model", "other-content"],
)
async def test_content_bearing_action_requires_matching_approval(
    db_session: AsyncSession,
    configured: None,
    httpx_mock: HTTPXMock,
    approved: ApprovedOutbound | None,
) -> None:
    await set_price(db_session)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run(action=REPORT_GENERATION, prompt="approved content", approved=approved)

    assert caught.value.status_code == 403
    assert caught.value.error.category == AiErrorCategory.SHARING_NOT_APPROVED
    assert httpx_mock.get_requests() == []
    assert await records(db_session) == []


def test_matching_approval_passes_the_check() -> None:
    gateway.require_approval(
        REPORT_GENERATION, AiProvider.OPENAI, "gpt-test", "approved content", approval()
    )


async def test_inference_test_refuses_any_prompt_but_the_fixed_one(
    db_session: AsyncSession, configured: None, httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    with pytest.raises(gateway.GatewayRejectionError) as caught:
        await run(prompt="Summarise report 42", approved=approval(content="Summarise report 42"))
    assert caught.value.error.category == AiErrorCategory.SHARING_NOT_APPROVED
    assert httpx_mock.get_requests() == []


# ── metadata only ──────────────────────────────────────────────────────────


async def test_usage_records_never_hold_secrets_prompts_or_responses(
    db_session: AsyncSession, configured: None, clock: list[datetime], httpx_mock: HTTPXMock
) -> None:
    await set_price(db_session)
    ok_response(httpx_mock, {"prompt_tokens": 1, "completion_tokens": 1})
    await run()
    httpx_mock.add_response(url=CHAT_URL, status_code=500, json={"error": SENTINEL})
    await run()

    dumped = json.dumps([list(row) for row in await records(db_session)], default=str)
    for forbidden in (FAKE_KEY, FAKE_KEY[-4:], INFERENCE_PROMPT, SENTINEL):
        assert forbidden not in dumped


def test_billability_mapping_for_unsent_and_refused_requests() -> None:
    def err(**kwargs: Any) -> AiAdapterError:
        from cti.services.ai.base import make_ai_error

        return AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR), **kwargs)

    assert gateway.billable_for_error(err(sent=False)) == gateway.Billable.NO
    assert gateway.billable_for_error(err(status_code=401)) == gateway.Billable.NO
    assert gateway.billable_for_error(err(status_code=402)) == gateway.Billable.UNKNOWN
    assert gateway.billable_for_error(err(status_code=None)) == gateway.Billable.UNKNOWN


def test_reservation_bound_is_bytes_plus_overhead_and_rounds_up() -> None:
    pricing = gateway.Pricing(Decimal("3"), Decimal("15"))
    prompt = "é" * 10  # 20 UTF-8 bytes
    assert gateway.input_token_upper_bound(prompt) == 84
    # (84 * 3 + 100 * 15) / 1e6 = 0.001752
    assert gateway.reservation_upper_bound(prompt, 100, pricing) == Decimal("0.001752")
    assert gateway.reservation_upper_bound(
        "x", 1, gateway.Pricing(Decimal("0.0001"), 0)
    ) == Decimal("0.000001")
    assert gateway.reservation_upper_bound(prompt, 100, None) is None
