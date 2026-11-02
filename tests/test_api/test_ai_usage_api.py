"""Settings → AI usage, guardrail and pricing API (#17)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import select

from cti.models.ai_usage import AiUsagePolicy, AiUsageRecord
from cti.models.audit import AuditEvent
from cti.services.ai import gateway
from cti.services.ai.base import INFERENCE_PROMPT
from tests.policy_helpers import non_admin_client

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient
    from pytest_httpx import HTTPXMock
    from sqlalchemy.ext.asyncio import AsyncSession

BASE = "/api/v1/settings/ai"
FAKE_KEY = "sk-test-not-a-real-key-usage-api-Zq9x"
CHAT_URL = "https://api.openai.com/v1/chat/completions"
POLICY = {
    "monthly_budget_usd": "10.5",
    "max_output_tokens": 256,
    "max_concurrent_requests": 3,
    "max_requests_per_minute": 20,
    "unpriced_model_policy": "permit",
}


async def configure(client: AsyncClient, provider: str = "openai") -> None:
    response = await client.put(f"{BASE}/providers/{provider}", json={"api_key": FAKE_KEY})
    assert response.status_code == 200, response.text


async def put_price(
    client: AsyncClient, provider: str = "openai", model: str = "gpt-test", price: str = "2"
) -> dict[str, Any]:
    response = await client.put(
        f"{BASE}/pricing/{provider}/{model}",
        json={"input_usd_per_mtok": price, "output_usd_per_mtok": price},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def events(db: AsyncSession, action: str) -> list[AuditEvent]:
    db.expunge_all()
    query = select(AuditEvent).where(AuditEvent.action == action)
    return list((await db.scalars(query.order_by(AuditEvent.occurred_at))).all())


async def usage_rows(db: AsyncSession) -> list[Any]:
    return list((await db.execute(select(AiUsageRecord.__table__))).all())


async def add_record(db: AsyncSession, started_at: datetime, **values: Any) -> AiUsageRecord:
    row: dict[str, Any] = {
        "action": "inference_test",
        "provider": "openai",
        "model": "gpt-test",
        "status": "succeeded",
        "billable": "yes",
        "started_at": started_at,
        "usage_source": "unknown",
        "cost_source": "unknown",
        "actor_label": "alice",
    }
    row.update(values)
    record = AiUsageRecord(**row)
    db.add(record)
    await db.commit()
    return record


def infer(model: str = "gpt-test", **extra: Any) -> dict[str, Any]:
    return {"model": model, "confirm": True, **extra}


# ── access control ─────────────────────────────────────────────────────────

NEW_ENDPOINTS = [
    ("GET", "/providers/openai/inference-test/preview?model=gpt-test", None),
    ("GET", "/usage", None),
    ("GET", "/usage/records", None),
    ("GET", "/usage-policy", None),
    ("PUT", "/usage-policy", POLICY),
    ("GET", "/pricing", None),
    ("PUT", "/pricing/openai/gpt-test", {"input_usd_per_mtok": "1", "output_usd_per_mtok": "1"}),
    ("DELETE", "/pricing/openai/gpt-test", None),
]


async def test_every_new_endpoint_requires_admin(
    app: FastAPI, client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    async with non_admin_client(app) as user:
        for method, path, body in NEW_ENDPOINTS:
            response = await user.request(method, f"{BASE}{path}", json=body)
            assert response.status_code == 403, (method, path, response.text)
    assert httpx_mock.get_requests() == []
    # Denied mutations are audited like the existing settings endpoints.
    assert [e.outcome for e in await events(db_session, "ai_usage_policy.update")] == ["denied"]
    assert [e.outcome for e in await events(db_session, "ai_pricing.update")] == ["denied"]
    assert [e.outcome for e in await events(db_session, "ai_pricing.delete")] == ["denied"]


# ── policy ─────────────────────────────────────────────────────────────────


async def test_policy_defaults_and_guarantee(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/usage-policy")

    assert response.status_code == 200
    body = response.json()
    assert {k: v for k, v in body.items() if k != "updated_at"} == {
        "monthly_budget_usd": None,
        "max_output_tokens": 1024,
        "max_concurrent_requests": 2,
        "max_requests_per_minute": 10,
        "unpriced_model_policy": "block",
        "guarantee": "local_estimate_only",
    }


async def test_policy_update_is_full_replacement_and_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.put(f"{BASE}/usage-policy", json=POLICY)

    assert response.status_code == 200, response.text
    assert response.json()["monthly_budget_usd"] == "10.5000"
    assert response.json()["max_output_tokens"] == 256
    assert (await client.get(f"{BASE}/usage-policy")).json() == response.json()

    cleared = await client.put(f"{BASE}/usage-policy", json={**POLICY, "monthly_budget_usd": None})
    assert cleared.json()["monthly_budget_usd"] is None

    first, second = await events(db_session, "ai_usage_policy.update")
    assert (first.outcome, first.resource_type, first.resource_id) == (
        "succeeded",
        "ai_usage_policy",
        "policy",
    )
    assert first.summary["before"]["max_output"] == 1024
    assert first.summary["after"] == {
        "monthly_budget_usd": "10.5000",
        "max_output": 256,
        "max_concurrent_requests": 3,
        "max_requests_per_minute": 20,
        "unpriced_model_policy": "permit",
    }
    assert second.summary["after"]["monthly_budget_usd"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"max_output_tokens": 0},
        {"max_output_tokens": 32001},
        {"max_concurrent_requests": 0},
        {"max_concurrent_requests": 51},
        {"max_requests_per_minute": 0},
        {"max_requests_per_minute": 601},
        {"unpriced_model_policy": "maybe"},
        {"monthly_budget_usd": "-1"},
        {"monthly_budget_usd": "abc"},
        {"monthly_budget_usd": "1.00001"},
        {"monthly_budget_usd": "NaN"},
        {"monthly_budget_usd": "Infinity"},
        {"monthly_budget_usd": "100000000"},
        {"monthly_budget_usd": 5},
    ],
)
async def test_policy_update_validates_ranges(
    client: AsyncClient, db_session: AsyncSession, change: dict[str, Any]
) -> None:
    response = await client.put(f"{BASE}/usage-policy", json={**POLICY, **change})

    assert response.status_code == 422
    assert await db_session.get(AiUsagePolicy, 1) is None


async def test_policy_update_requires_every_field(client: AsyncClient) -> None:
    partial = {k: v for k, v in POLICY.items() if k != "max_requests_per_minute"}
    assert (await client.put(f"{BASE}/usage-policy", json=partial)).status_code == 422


# ── pricing ────────────────────────────────────────────────────────────────


async def test_pricing_crud_with_path_model_ids_and_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    assert (await client.get(f"{BASE}/pricing")).json() == {"items": []}

    created = await put_price(client, "openrouter", "anthropic/claude-x", "3.25")
    assert created["model"] == "anthropic/claude-x"
    assert created["input_usd_per_mtok"] == "3.250000"
    await put_price(client, "openrouter", "anthropic/claude-x", "4")
    await put_price(client, "openai", "gpt-test", "1")

    listed = (await client.get(f"{BASE}/pricing")).json()["items"]
    assert [(i["provider"], i["model"], i["output_usd_per_mtok"]) for i in listed] == [
        ("openai", "gpt-test", "1.000000"),
        ("openrouter", "anthropic/claude-x", "4.000000"),
    ]

    deleted = await client.delete(f"{BASE}/pricing/openrouter/anthropic/claude-x")
    assert deleted.status_code == 204
    missing = await client.delete(f"{BASE}/pricing/openrouter/anthropic/claude-x")
    assert missing.status_code == 404

    updates = await events(db_session, "ai_pricing.update")
    assert [e.summary["before"] for e in updates] == [
        None,
        {"input_usd_per_mtok": "3.250000", "output_usd_per_mtok": "3.250000"},
        None,
    ]
    assert updates[0].resource_label == "anthropic/claude-x"
    deletes = await events(db_session, "ai_pricing.delete")
    assert [(e.outcome, e.summary.get("status")) for e in deletes] == [
        ("succeeded", None),
        ("failed", 404),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"input_usd_per_mtok": "-1", "output_usd_per_mtok": "1"},
        {"input_usd_per_mtok": "1", "output_usd_per_mtok": "1.0000001"},
        {"input_usd_per_mtok": "x", "output_usd_per_mtok": "1"},
        {"input_usd_per_mtok": 1, "output_usd_per_mtok": 1},
        {"input_usd_per_mtok": "1"},
    ],
)
async def test_pricing_validation(client: AsyncClient, body: dict[str, Any]) -> None:
    response = await client.put(f"{BASE}/pricing/openai/gpt-test", json=body)
    assert response.status_code == 422


async def test_pricing_rejects_unknown_provider(client: AsyncClient) -> None:
    response = await client.put(
        f"{BASE}/pricing/acme/m", json={"input_usd_per_mtok": "1", "output_usd_per_mtok": "1"}
    )
    assert response.status_code == 422


# ── preview ────────────────────────────────────────────────────────────────


async def test_preview_unpriced_is_blocked_and_makes_no_call(
    client: AsyncClient, httpx_mock: HTTPXMock
) -> None:
    response = await client.get(f"{BASE}/providers/openai/inference-test/preview?model=gpt-test")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openai",
        "model": "gpt-test",
        "action": "inference_test",
        "content": INFERENCE_PROMPT,
        "max_output_tokens": 1024,
        "pricing_known": False,
        "estimated_max_cost_usd": None,
        "policy_decision": "blocked_unpriced",
        "destination_note": "Sent to OpenAI (api.openai.com)",
    }
    assert httpx_mock.get_requests() == []


async def test_preview_priced_and_over_budget(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await put_price(client, "xai", "grok-test", "1000")
    url = f"{BASE}/providers/xai/inference-test/preview?model=grok-test"

    allowed = (await client.get(url)).json()
    assert allowed["policy_decision"] == "allowed"
    assert allowed["pricing_known"] is True
    assert allowed["estimated_max_cost_usd"] == "1.118000"  # (30 + 64 + 1024) * 1000 / 1e6
    assert allowed["destination_note"] == "Sent to xAI (Grok) (api.x.ai)"

    # max_output_tokens 256: (94 + 256) * 1000 / 1e6 = 0.35 > 0.3.
    await client.put(f"{BASE}/usage-policy", json={**POLICY, "monthly_budget_usd": "0.3"})
    over = (await client.get(url)).json()
    assert over["policy_decision"] == "over_budget"
    assert over["max_output_tokens"] == 256

    permit_unpriced = (
        await client.get(f"{BASE}/providers/xai/inference-test/preview?model=other")
    ).json()
    assert permit_unpriced["policy_decision"] == "allowed"
    assert permit_unpriced["estimated_max_cost_usd"] is None


async def test_preview_validates_model(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/providers/openai/inference-test/preview?model=a%0Ab")
    assert response.status_code == 422


# ── inference test through the gateway ─────────────────────────────────────


async def test_default_policy_blocks_unpriced_inference_without_calling_provider(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)

    response = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())

    assert response.status_code == 409
    assert response.json()["category"] == "model_blocked_unpriced"
    assert httpx_mock.get_requests() == []
    assert await usage_rows(db_session) == []
    [event] = await events(db_session, "ai.request")
    assert (event.outcome, event.summary["error_code"], event.summary["status"]) == (
        "failed",
        "model_blocked_unpriced",
        409,
    )


async def test_inference_returns_usage_and_records_retry_of(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    await put_price(client)
    httpx_mock.add_response(
        url=CHAT_URL, json={"usage": {"prompt_tokens": 10, "completion_tokens": 2}}
    )
    previous = uuid.uuid4()

    response = await client.post(
        f"{BASE}/providers/openai/inference-test", json=infer(retry_of=str(previous))
    )

    assert response.status_code == 200, response.text
    usage = response.json()["usage"]
    assert usage["input_tokens"] == 10 and usage["output_tokens"] == 2
    assert usage["usage_source"] == "provider_reported"
    assert (usage["cost_usd"], usage["cost_source"]) == ("0.000024", "estimated")
    [row] = await usage_rows(db_session)
    assert str(row.id) == usage["record_id"]
    assert row.retry_of == previous
    assert row.actor_label == "Test Key"
    sent = json.loads(httpx_mock.get_request().content)  # type: ignore[union-attr]
    assert sent["max_completion_tokens"] == 1024
    # The ai.request audit trail is unchanged: initiated + succeeded.
    assert [e.outcome for e in await events(db_session, "ai.request")] == [
        "initiated",
        "succeeded",
    ]


async def test_failed_inference_reports_usage_record_with_unknown_cost(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    await put_price(client)
    httpx_mock.add_response(url=CHAT_URL, status_code=502)

    response = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False and body["error"]["category"] == "provider_error"
    assert body["usage"]["cost_usd"] is None and body["usage"]["cost_source"] == "unknown"
    [row] = await usage_rows(db_session)
    assert (row.status, row.billable) == ("failed", "unknown")


async def test_budget_exceeded_returns_402_without_provider_call(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    await put_price(client, price="1000")
    await client.put(f"{BASE}/usage-policy", json={**POLICY, "monthly_budget_usd": "0.1"})

    response = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())

    assert response.status_code == 402
    assert response.json()["category"] == "budget_exceeded"
    assert "not a provider billing limit" in response.json()["message"]
    assert httpx_mock.get_requests() == []
    assert await usage_rows(db_session) == []


async def test_local_rate_limit_returns_429(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    await put_price(client)
    await client.put(f"{BASE}/usage-policy", json={**POLICY, "max_requests_per_minute": 1})
    httpx_mock.add_response(url=CHAT_URL, json={})

    first = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())
    second = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["category"] == "local_rate_limited"
    assert len(httpx_mock.get_requests()) == 1
    assert len(await usage_rows(db_session)) == 1


async def test_failed_initiated_audit_leaves_no_reservation(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cti.services import audit

    await configure(client)
    await put_price(client)

    async def broken_disclosure(**_: object) -> None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Audit log unavailable")

    monkeypatch.setattr(audit, "begin_disclosure", broken_disclosure)
    response = await client.post(f"{BASE}/providers/openai/inference-test", json=infer())

    assert response.status_code == 503
    assert httpx_mock.get_requests() == []
    assert await usage_rows(db_session) == []


async def test_model_listing_and_check_never_create_usage_records(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    httpx_mock.add_response(
        url="https://api.openai.com/v1/models", json={"data": []}, is_reusable=True
    )

    assert (await client.post(f"{BASE}/providers/openai/check")).status_code == 200
    assert (await client.get(f"{BASE}/providers/openai/models?refresh=true")).status_code == 200

    assert await usage_rows(db_session) == []


# ── usage report ───────────────────────────────────────────────────────────


async def test_usage_report_totals_breakdowns_and_unknowns(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.put(f"{BASE}/usage-policy", json={**POLICY, "monthly_budget_usd": "1"})
    day_one = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    day_two = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    # Known cost and tokens.
    await add_record(
        db_session,
        day_one,
        input_tokens=100,
        output_tokens=10,
        usage_source="provider_reported",
        reserved_usd=Decimal("0.5"),
        cost_usd=Decimal("0.01"),
        cost_source="estimated",
    )
    # Billed, no usage reported: tokens and cost unknown; reservation committed.
    await add_record(db_session, day_one, reserved_usd=Decimal("0.2"))
    # Refused by the provider: committed 0, but its usage and cost are still
    # unknown (NULL), so it counts toward both unknown counters.
    await add_record(db_session, day_two, status="failed", billable="no", reserved_usd=Decimal("9"))
    # Possibly billed failure on another model, unpriced and permitted.
    await add_record(
        db_session,
        day_two,
        status="failed",
        billable="unknown",
        model="gpt-other",
        input_tokens=5,
        usage_source="provider_reported",
    )
    # In flight.
    await add_record(
        db_session, day_two, status="reserved", billable="unknown", reserved_usd=Decimal("0.3")
    )
    # Another month: excluded.
    await add_record(
        db_session, datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC), cost_usd=Decimal("5")
    )

    response = await client.get(f"{BASE}/usage?month=2026-11")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == {
        "month": "2026-11",
        "start": "2026-11-01T00:00:00Z",
        "end": "2026-12-01T00:00:00Z",
        "timezone": "UTC",
    }
    assert body["actions_in_scope"] == ["inference_test"]
    assert body["guarantee"] == "local_estimate_only"
    assert body["totals"] == {
        "requests": 5,
        "succeeded": 2,
        "failed": 2,
        "cancelled": 0,
        "reserved": 1,
        "input_tokens": 105,
        "output_tokens": 10,
        "token_unknown_requests": 4,
        "estimated_cost_usd": "0.010000",
        "cost_unknown_requests": 4,
        "committed_usd": "0.510000",
    }
    assert body["budget"] == {
        "monthly_budget_usd": "1.0000",
        "committed_usd": "0.510000",
        "remaining_usd": "0.490000",
    }
    pairs = {(p["provider"], p["model"]): p for p in body["by_provider_model"]}
    assert set(pairs) == {("openai", "gpt-other"), ("openai", "gpt-test")}
    assert pairs[("openai", "gpt-other")]["input_tokens"] == 5
    assert pairs[("openai", "gpt-other")]["token_unknown_requests"] == 1
    assert pairs[("openai", "gpt-test")]["committed_usd"] == "0.510000"
    assert [(d["date"], d["requests"]) for d in body["by_day"]] == [
        ("2026-11-02", 2),
        ("2026-11-03", 3),
    ]


async def test_usage_report_counts_unknowns_regardless_of_billable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Unknown is never zero: NULL usage/cost counts even when billable is "no"."""
    started = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    await add_record(db_session, started, status="failed", billable="no", reserved_usd=Decimal("1"))
    await add_record(
        db_session,
        started,
        status="failed",
        billable="no",
        input_tokens=7,
        output_tokens=0,
        usage_source="provider_reported",
        cost_usd=Decimal("0"),
        cost_source="estimated",
    )

    totals = (await client.get(f"{BASE}/usage?month=2026-11")).json()["totals"]

    assert totals["input_tokens"] == 7
    assert totals["token_unknown_requests"] == 1
    assert totals["estimated_cost_usd"] == "0.000000"
    assert totals["cost_unknown_requests"] == 1
    assert totals["committed_usd"] == "0.000000"


async def test_usage_report_aggregates_in_sql_without_loading_records(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The report must not materialize the month's records (only bounded aggregates)."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine = db_session.bind
    assert isinstance(engine, AsyncEngine)
    for hour in range(3):
        await add_record(db_session, datetime(2026, 11, 2, hour, tzinfo=UTC))
    statements: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = await client.get(f"{BASE}/usage?month=2026-11")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    assert response.status_code == 200
    assert response.json()["totals"]["requests"] == 3
    usage_reads = [s for s in statements if "FROM ai_usage_records" in s]
    # Totals, days and the provider/model breakdown; the group count is only
    # needed once the breakdown is full.
    assert len(usage_reads) == 3, usage_reads
    totals_query, day_query, pair_query = usage_reads
    assert "GROUP BY" not in totals_query
    assert "GROUP BY" in day_query
    assert "GROUP BY" in pair_query
    assert "LIMIT" in pair_query
    for query in usage_reads:
        # An entity load would select per-record columns such as the id or actor.
        assert "ai_usage_records.id" not in query
        assert "ai_usage_records.actor_label" not in query


TOTAL_FIELDS = (
    "requests",
    "succeeded",
    "failed",
    "cancelled",
    "reserved",
    "input_tokens",
    "output_tokens",
    "token_unknown_requests",
    "estimated_cost_usd",
    "cost_unknown_requests",
    "committed_usd",
)


def _field_sum(rows: list[dict[str, Any]], name: str) -> Any:
    if name.endswith("_usd"):
        return f"{sum((Decimal(row[name]) for row in rows), Decimal(0)):.6f}"
    return sum(row[name] for row in rows)


async def test_usage_breakdown_is_bounded_with_exact_other_bucket(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """More than 100 models: the top 100 are listed and the rest summed, never dropped."""
    from cti.services.ai_settings_service import USAGE_BREAKDOWN_LIMIT

    started = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    models = USAGE_BREAKDOWN_LIMIT + 37
    records = []
    for index in range(models):
        # Model i gets 1 + i % 4 requests, so the ordering has ties to break.
        for repeat in range(1 + index % 4):
            records.append(
                AiUsageRecord(
                    action="inference_test",
                    provider="openai" if index % 2 else "anthropic",
                    model=f"model-{index:03d}",
                    status="failed" if repeat == 2 else "succeeded",
                    billable="yes",
                    started_at=started + timedelta(days=index % 3),
                    input_tokens=None if repeat == 1 else index,
                    output_tokens=3,
                    usage_source="provider_reported",
                    reserved_usd=Decimal("0.5"),
                    cost_usd=None if repeat == 3 else Decimal(index) / 1000,
                    cost_source="estimated",
                    actor_label="alice",
                )
            )
    db_session.add_all(records)
    await db_session.commit()

    body = (await client.get(f"{BASE}/usage?month=2026-11")).json()

    rows = body["by_provider_model"]
    assert body["by_provider_model_limit"] == USAGE_BREAKDOWN_LIMIT
    assert len(rows) == USAGE_BREAKDOWN_LIMIT
    assert body["by_provider_model_omitted_groups"] == models - USAGE_BREAKDOWN_LIMIT
    # Most requests first, then provider and model.
    keys = [(-row["requests"], row["provider"], row["model"]) for row in rows]
    assert keys == sorted(keys)
    listed = {row["model"] for row in rows}
    omitted = [1 + i % 4 for i in range(models) if f"model-{i:03d}" not in listed]
    assert min(row["requests"] for row in rows) >= max(omitted)
    other = body["by_provider_model_other"]
    assert other is not None
    assert other["requests"] >= 1
    for name in TOTAL_FIELDS:
        assert body["totals"][name] == _field_sum([*rows, other], name), name
    assert body["totals"]["requests"] == len(records)
    assert len(body["by_day"]) == 3


async def test_usage_breakdown_at_the_limit_has_no_other_bucket(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from cti.services.ai_settings_service import USAGE_BREAKDOWN_LIMIT

    started = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    db_session.add_all(
        AiUsageRecord(
            action="inference_test",
            provider="openai",
            model=f"model-{index:03d}",
            status="succeeded",
            billable="yes",
            started_at=started,
            usage_source="unknown",
            cost_source="unknown",
        )
        for index in range(USAGE_BREAKDOWN_LIMIT)
    )
    await db_session.commit()

    body = (await client.get(f"{BASE}/usage?month=2026-11")).json()

    assert len(body["by_provider_model"]) == USAGE_BREAKDOWN_LIMIT
    assert body["by_provider_model_omitted_groups"] == 0
    assert body["by_provider_model_other"] is None


async def test_usage_report_sums_money_exactly(db_session: AsyncSession) -> None:
    """SQLite NUMERIC sums are floating point; the report must equal Decimal sums.

    Mirrors the R4 proof: 1000 x 99999999.999999 + 0.000001 must not round, for
    both the estimated cost and committed spend (including reservation-based,
    stale and non-billable contributions).
    """
    from cti.services.ai_settings_service import usage_report

    large = Decimal("99999999.999999")
    small = Decimal("0.000001")
    started = datetime(2026, 11, 2, tzinfo=UTC)
    shapes: list[dict[str, Any]] = [{"cost_usd": large} for _ in range(1000)]
    shapes.append({"cost_usd": small})
    # Committed from the reservation: billed with unknown cost, possibly billed,
    # a reservation (it stays committed even once stale), and a refusal that
    # commits nothing.
    shapes.append({"reserved_usd": large, "billable": "yes"})
    shapes.append({"reserved_usd": small, "billable": "unknown", "status": "failed"})
    shapes.append({"reserved_usd": large, "billable": "unknown", "status": "reserved"})
    shapes.append({"reserved_usd": large, "billable": "no", "status": "failed"})
    expected_cost = Decimal(0)
    expected_committed = Decimal(0)
    for shape in shapes:
        values: dict[str, Any] = {
            "action": "inference_test",
            "provider": "openai",
            "model": "m",
            "status": "succeeded",
            "billable": "yes",
            "started_at": started,
            "usage_source": "unknown",
            "cost_source": "estimated" if "cost_usd" in shape else "unknown",
            **shape,
        }
        db_session.add(AiUsageRecord(**values))
        expected_cost += values.get("cost_usd") or Decimal(0)
        expected_committed += gateway.committed_contribution(
            status=values["status"],
            billable=values["billable"],
            reserved_usd=values.get("reserved_usd"),
            cost_usd=values.get("cost_usd"),
        )
    await db_session.commit()

    report = await usage_report(db_session, 2026, 11)

    assert report.totals.estimated_cost_usd == f"{large * 1000 + small:.6f}"
    assert report.totals.estimated_cost_usd == f"{expected_cost:.6f}"
    assert report.totals.committed_usd == f"{expected_committed:.6f}"
    assert report.budget.committed_usd == f"{expected_committed:.6f}"
    [pair] = report.by_provider_model
    assert pair.committed_usd == f"{expected_committed:.6f}"
    start, end = gateway.month_bounds(2026, 11)
    assert await gateway.committed_spend(db_session, start, end) == expected_committed


async def test_usage_month_boundary_is_utc(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_record(db_session, datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC))
    await add_record(db_session, datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC))

    november = (await client.get(f"{BASE}/usage?month=2026-11")).json()
    december = (await client.get(f"{BASE}/usage?month=2026-12")).json()

    assert november["totals"]["requests"] == 1
    assert [d["date"] for d in november["by_day"]] == ["2026-11-30"]
    assert december["totals"]["requests"] == 1
    assert [d["date"] for d in december["by_day"]] == ["2026-12-01"]
    assert december["period"]["end"] == "2027-01-01T00:00:00Z"


async def test_usage_defaults_to_current_utc_month_and_validates(client: AsyncClient) -> None:
    body = (await client.get(f"{BASE}/usage")).json()
    now = datetime.now(UTC)
    assert body["period"]["month"] == f"{now.year:04d}-{now.month:02d}"
    assert body["totals"]["requests"] == 0
    assert body["totals"]["committed_usd"] == "0.000000"
    assert body["budget"]["remaining_usd"] is None

    for bad in ("2026-13", "2026-1", "26-11", "1999-12", "9999-12", "2026-11-01", "x"):
        assert (await client.get(f"{BASE}/usage?month={bad}")).status_code == 422, bad
        assert (await client.get(f"{BASE}/usage/records?month={bad}")).status_code == 422, bad


@pytest.mark.parametrize(
    ("month", "status"),
    [("1999-12", 422), ("2000-01", 200), ("9999-11", 200), ("9999-12", 422)],
)
async def test_usage_month_range_edges(client: AsyncClient, month: str, status: int) -> None:
    """Periods run 2000-01..9999-11; 9999-12 would need a year-10000 end bound."""
    for path in ("/usage", "/usage/records"):
        response = await client.get(f"{BASE}{path}?month={month}")
        assert response.status_code == status, (path, response.text)


# ── usage records ──────────────────────────────────────────────────────────


async def test_usage_records_paginate_newest_first_with_stale_flag(
    client: AsyncClient, db_session: AsyncSession, test_api_key: tuple[str, str]
) -> None:
    now = datetime.now(UTC)
    month = f"{now.year:04d}-{now.month:02d}"
    start = gateway.month_bounds(now.year, now.month)[0]
    oldest = await add_record(db_session, start, status="reserved", billable="unknown")
    middle = await add_record(db_session, start + timedelta(seconds=1), cost_usd=Decimal("0.5"))
    newest = await add_record(
        db_session, now, status="reserved", billable="unknown", reserved_usd=Decimal("0.1")
    )

    first = (await client.get(f"{BASE}/usage/records?month={month}&limit=2")).json()
    assert [item["id"] for item in first["items"]] == [str(newest.id), str(middle.id)]
    assert first["next_before"] == str(middle.id)
    newest_item = first["items"][0]
    assert newest_item["stale"] is False
    assert newest_item["reserved_usd"] == "0.100000"
    assert newest_item["cost_usd"] is None
    assert "actor_user_id" not in newest_item
    assert newest_item["actor_label"] == "alice"

    second = (
        await client.get(f"{BASE}/usage/records?month={month}&limit=2&before={middle.id}")
    ).json()
    assert [item["id"] for item in second["items"]] == [str(oldest.id)]
    assert second["next_before"] is None
    if now - start > gateway.STALE_RESERVATION_AFTER:
        assert second["items"][0]["stale"] is True

    bad_cursor = await client.get(f"{BASE}/usage/records?month={month}&before={uuid.uuid4()}")
    assert bad_cursor.status_code == 422
    assert (await client.get(f"{BASE}/usage/records?limit=0")).status_code == 422
    assert (await client.get(f"{BASE}/usage/records?limit=201")).status_code == 422


async def test_stale_flag_marks_orphaned_reservations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    started = datetime.now(UTC) - gateway.STALE_RESERVATION_AFTER - timedelta(seconds=5)
    record = await add_record(
        db_session, started, status="reserved", billable="unknown", reserved_usd=Decimal("0.25")
    )
    month = f"{started.year:04d}-{started.month:02d}"

    [item] = (await client.get(f"{BASE}/usage/records?month={month}")).json()["items"]
    assert item["id"] == str(record.id)
    assert (item["status"], item["stale"]) == ("reserved", True)
    report = (await client.get(f"{BASE}/usage?month={month}")).json()
    assert report["totals"]["committed_usd"] == "0.250000"  # still counts as spend


async def test_usage_api_never_exposes_secrets(
    client: AsyncClient, db_session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    await configure(client)
    await put_price(client)
    httpx_mock.add_response(url=CHAT_URL, json={"usage": {"prompt_tokens": 1}})
    assert (await client.post(f"{BASE}/providers/openai/inference-test", json=infer())).is_success

    for path in ("/usage", "/usage/records", "/usage-policy", "/pricing"):
        text = (await client.get(f"{BASE}{path}")).text
        assert FAKE_KEY not in text and FAKE_KEY[-4:] not in text, path
        assert INFERENCE_PROMPT not in text, path
    dumped = json.dumps([list(r) for r in await usage_rows(db_session)], default=str)
    assert FAKE_KEY not in dumped and INFERENCE_PROMPT not in dumped
