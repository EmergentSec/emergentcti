from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Numeric, and_, case, cast, delete, func, or_, select

from cti.core.security import decrypt_config, encrypt_config
from cti.models.ai import AiProvider, AiProviderConfig, AiSettingsRecord
from cti.models.ai_usage import (
    AiAction,
    AiModelPricing,
    AiUsagePolicy,
    AiUsageRecord,
    UnpricedModelPolicy,
    UsageStatus,
)
from cti.schemas.ai import (
    AiCheckResult,
    AiDefault,
    AiDefaultUpdate,
    AiError,
    AiErrorCategory,
    AiInferencePreview,
    AiInferenceResult,
    AiModel,
    AiModelList,
    AiModelPricingList,
    AiModelPricingOut,
    AiModelPricingUpdate,
    AiProviderStatus,
    AiSettings,
    AiUsageBudget,
    AiUsageByDay,
    AiUsageByProviderModel,
    AiUsagePeriod,
    AiUsagePolicyOut,
    AiUsagePolicyUpdate,
    AiUsageRecordItem,
    AiUsageRecordPage,
    AiUsageReport,
    AiUsageSummary,
    AiUsageTotals,
    ModelSource,
)
from cti.services.ai import gateway
from cti.services.ai.base import INFERENCE_PROMPT, AiAdapterError, make_ai_error, sorted_models
from cti.services.ai.catalog import fallback_models
from cti.services.ai.registry import get_adapter

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from cti.services.audit import Actor

    #: Awaited immediately before the provider is contacted (never on a cache
    #: hit or when the provider is not configured). Routes use it to write the
    #: ``ai.request`` initiated audit event; if it raises, nothing is sent.
    BeforeProviderCall = Callable[[], Awaitable[None]]

MODEL_CACHE_TTL = timedelta(hours=1)

_PROVIDER_METADATA: dict[AiProvider, tuple[str, str]] = {
    AiProvider.ANTHROPIC: ("Anthropic", "https://console.anthropic.com/settings/keys"),
    AiProvider.OPENAI: ("OpenAI", "https://platform.openai.com/api-keys"),
    AiProvider.OPENROUTER: ("OpenRouter", "https://openrouter.ai/settings/keys"),
    AiProvider.XAI: ("xAI (Grok)", "https://console.x.ai/"),
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AiSettingsServiceError(Exception):
    def __init__(self, status_code: int, error: AiError) -> None:
        super().__init__(error.category.value)
        self.status_code = status_code
        self.error = error


def _provider_status(
    provider: AiProvider,
    config: AiProviderConfig | None,
) -> AiProviderStatus:
    display_name, setup_url = _PROVIDER_METADATA[provider]
    return AiProviderStatus(
        provider=provider,
        display_name=display_name,
        configured=config is not None,
        key_hint=config.key_hint if config is not None else None,
        models_fetched_at=config.models_fetched_at if config is not None else None,
        last_check_status=config.last_check_status if config is not None else None,
        last_check_category=(
            AiErrorCategory(config.last_check_category)
            if config is not None and config.last_check_category is not None
            else None
        ),
        last_checked_at=config.last_checked_at if config is not None else None,
        setup_url=setup_url,
    )


async def _get_provider_config(
    db: AsyncSession,
    provider: AiProvider,
) -> AiProviderConfig | None:
    return await db.scalar(select(AiProviderConfig).where(AiProviderConfig.provider == provider))


async def _require_provider_config(
    db: AsyncSession,
    provider: AiProvider,
    *,
    status_code: int = 409,
) -> AiProviderConfig:
    config = await _get_provider_config(db, provider)
    if config is None:
        raise AiSettingsServiceError(
            status_code,
            make_ai_error(AiErrorCategory.NOT_CONFIGURED),
        )
    return config


def _decrypt_api_key(config: AiProviderConfig) -> str:
    try:
        payload = decrypt_config(config.credentials_encrypted)
        api_key = payload["api_key"]
    except Exception:  # the encrypted payload must never escape through the error
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR)) from None
    if not isinstance(api_key, str) or not api_key:
        raise AiAdapterError(make_ai_error(AiErrorCategory.PROVIDER_ERROR))
    return api_key


def _cached_models(config: AiProviderConfig) -> list[AiModel] | None:
    if config.model_cache is None:
        return None
    try:
        return [AiModel.model_validate(model) for model in config.model_cache]
    except (TypeError, ValueError):
        return None


async def _flush_with_orphan_cleanup(db: AsyncSession) -> None:
    settings = await db.get(AiSettingsRecord, 1)
    if (
        settings is not None
        and settings.default_provider is None
        and settings.default_model is not None
    ):
        settings.default_model = None
        settings.default_model_is_custom = False
    await db.flush()


async def get_settings(db: AsyncSession) -> AiSettings:
    configured = {
        AiProvider(item.provider): item
        for item in (await db.scalars(select(AiProviderConfig))).all()
    }
    settings = await db.get(AiSettingsRecord, 1)
    default = None
    if (
        settings is not None
        and settings.default_provider is not None
        and settings.default_model is not None
    ):
        default = AiDefault(
            provider=AiProvider(settings.default_provider),
            model=settings.default_model,
            is_custom=settings.default_model_is_custom,
        )
    return AiSettings(
        providers=[_provider_status(provider, configured.get(provider)) for provider in AiProvider],
        default=default,
    )


async def save_provider_key(
    db: AsyncSession,
    provider: AiProvider,
    api_key: str,
) -> AiProviderStatus:
    config = await _get_provider_config(db, provider)
    encrypted = encrypt_config({"api_key": api_key})
    key_hint = api_key[-4:] if len(api_key) >= 12 else None
    if config is None:
        config = AiProviderConfig(
            provider=provider,
            credentials_encrypted=encrypted,
            key_hint=key_hint,
        )
        db.add(config)
    else:
        config.credentials_encrypted = encrypted
        config.key_hint = key_hint
        config.model_cache = None
        config.models_fetched_at = None
        config.last_check_status = None
        config.last_check_category = None
        config.last_checked_at = None
    await _flush_with_orphan_cleanup(db)
    return _provider_status(provider, config)


async def delete_provider(db: AsyncSession, provider: AiProvider) -> None:
    config = await _require_provider_config(db, provider, status_code=404)
    settings = await db.get(AiSettingsRecord, 1)
    if settings is not None and settings.default_provider == provider:
        settings.default_provider = None
        settings.default_model = None
        settings.default_model_is_custom = False
    await db.delete(config)
    await _flush_with_orphan_cleanup(db)


async def check_provider(
    db: AsyncSession,
    provider: AiProvider,
    *,
    before_provider_call: BeforeProviderCall | None = None,
) -> AiCheckResult:
    config = await _require_provider_config(db, provider)
    if before_provider_call is not None:
        await before_provider_call()
    checked_at = _now()
    try:
        api_key = _decrypt_api_key(config)
        await get_adapter(provider).check(api_key)
    except AiAdapterError as exc:
        config.last_check_status = "error"
        config.last_check_category = exc.error.category.value
        config.last_checked_at = checked_at
        await _flush_with_orphan_cleanup(db)
        return AiCheckResult(ok=False, error=exc.error, checked_at=checked_at)

    config.last_check_status = "ok"
    config.last_check_category = None
    config.last_checked_at = checked_at
    await _flush_with_orphan_cleanup(db)
    return AiCheckResult(ok=True, error=None, checked_at=checked_at)


async def list_models(
    db: AsyncSession,
    provider: AiProvider,
    *,
    refresh: bool,
    before_provider_call: BeforeProviderCall | None = None,
) -> AiModelList:
    config = await _require_provider_config(db, provider)
    cached = _cached_models(config)
    now = _now()
    if (
        not refresh
        and cached is not None
        and config.models_fetched_at is not None
        and now - config.models_fetched_at < MODEL_CACHE_TTL
    ):
        return AiModelList(
            provider=provider,
            source=ModelSource.CACHE,
            fetched_at=config.models_fetched_at,
            models=cached,
            error=None,
        )

    if before_provider_call is not None:
        await before_provider_call()
    try:
        api_key = _decrypt_api_key(config)
        models = await get_adapter(provider).list_models(api_key)
    except AiAdapterError as exc:
        if cached is not None:
            return AiModelList(
                provider=provider,
                source=ModelSource.CACHE,
                fetched_at=config.models_fetched_at,
                models=cached,
                error=exc.error,
            )
        return AiModelList(
            provider=provider,
            source=ModelSource.FALLBACK,
            fetched_at=None,
            models=sorted_models(fallback_models(provider)),
            error=exc.error,
        )

    fetched_at = _now()
    config.model_cache = [model.model_dump(mode="json") for model in models]
    config.models_fetched_at = fetched_at
    await _flush_with_orphan_cleanup(db)
    return AiModelList(
        provider=provider,
        source=ModelSource.LIVE,
        fetched_at=fetched_at,
        models=models,
        error=None,
    )


async def set_default(
    db: AsyncSession,
    update: AiDefaultUpdate,
) -> AiDefault:
    config = await _require_provider_config(db, update.provider)
    if not update.is_custom:
        candidates = _cached_models(config)
        if candidates is None:
            candidates = fallback_models(update.provider)
        if update.model not in {model.id for model in candidates}:
            raise AiSettingsServiceError(
                422,
                AiError(
                    category=AiErrorCategory.MODEL_UNAVAILABLE,
                    message=(
                        "That model is not in the stored provider model list. "
                        "Choose a listed model or use a custom ID."
                    ),
                ),
            )

    settings = await db.get(AiSettingsRecord, 1)
    if settings is None:
        settings = AiSettingsRecord(id=1)
        db.add(settings)
    settings.default_provider = update.provider
    settings.default_model = update.model
    settings.default_model_is_custom = update.is_custom
    await _flush_with_orphan_cleanup(db)
    return AiDefault(
        provider=update.provider,
        model=update.model,
        is_custom=update.is_custom,
    )


async def clear_default(db: AsyncSession) -> None:
    settings = await db.get(AiSettingsRecord, 1)
    if settings is None:
        return
    settings.default_provider = None
    settings.default_model = None
    settings.default_model_is_custom = False
    await _flush_with_orphan_cleanup(db)


async def inference_test(
    db: AsyncSession,
    provider: AiProvider,
    model: str,
    *,
    actor: Actor,
    retry_of: uuid.UUID | None = None,
    before_provider_call: BeforeProviderCall | None = None,
    db_factory: gateway.SessionContextFactory | None = None,
) -> AiInferenceResult:
    """Send the fixed inference prompt through the accounting gateway.

    Guardrail rejections raise :class:`AiSettingsServiceError` (402/409/429)
    before anything is sent; they write no usage record.
    """
    await _require_provider_config(db, provider)
    try:
        outcome = await gateway.run_inference(
            db_factory or gateway.independent_session,
            actor=actor,
            action=AiAction.INFERENCE_TEST,
            provider=provider,
            model=model,
            prompt=INFERENCE_PROMPT,
            approved=None,
            retry_of=retry_of,
            adapter=get_adapter(provider),
            before_dispatch=before_provider_call,
        )
    except gateway.GatewayRejectionError as exc:
        raise AiSettingsServiceError(exc.status_code, exc.error) from None
    usage = None
    if outcome.record_id is not None:
        usage = AiUsageSummary(
            record_id=outcome.record_id,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            usage_source=outcome.usage_source.value,
            cost_usd=gateway.format_usd(outcome.cost_usd),
            cost_source=outcome.cost_source.value,
        )
    return AiInferenceResult(
        ok=outcome.ok, error=outcome.error, latency_ms=outcome.latency_ms, usage=usage
    )


async def inference_preview(
    db: AsyncSession,
    provider: AiProvider,
    model: str,
) -> AiInferencePreview:
    """What a confirmed inference test would send, and whether policy allows it.

    Makes no provider call. Concurrency and rate limits are checked only at
    send time, so ``allowed`` is not a promise.
    """
    policy = await gateway.read_policy(db)
    pricing = await gateway.read_pricing(db, provider, model)
    reserved = gateway.reservation_upper_bound(INFERENCE_PROMPT, policy.max_output_tokens, pricing)
    decision: str = "allowed"
    if pricing is None and policy.unpriced_model_policy != UnpricedModelPolicy.PERMIT:
        decision = "blocked_unpriced"
    elif policy.monthly_budget_usd is not None:
        start, end = gateway.month_bounds(*gateway.current_month())
        committed = await gateway.committed_spend(db, start, end)
        if committed + (reserved or Decimal(0)) > Decimal(policy.monthly_budget_usd):
            decision = "over_budget"
    display_name, _setup_url = _PROVIDER_METADATA[provider]
    return AiInferencePreview.model_validate(
        {
            "provider": provider,
            "model": model,
            "action": AiAction.INFERENCE_TEST.value,
            "content": INFERENCE_PROMPT,
            "max_output_tokens": policy.max_output_tokens,
            "pricing_known": pricing is not None,
            "estimated_max_cost_usd": gateway.format_usd(reserved),
            "policy_decision": decision,
            "destination_note": f"Sent to {display_name} ({get_adapter(provider).host})",
        }
    )


# ── Usage report (#17) ─────────────────────────────────────────────────


def _budget_str(value: Decimal | None) -> str | None:
    return None if value is None else str(Decimal(value).quantize(Decimal("0.0001")))


def _price_str(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.000001")))


def _count_where(condition: ColumnElement[bool]) -> ColumnElement[int]:
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


@dataclass
class _Totals:
    requests: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    reserved: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_unknown_requests: int = 0
    estimated_cost_usd: Decimal = field(default_factory=Decimal)
    cost_unknown_requests: int = 0
    committed_usd: Decimal = field(default_factory=Decimal)

    def add(self, other: _Totals) -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def fields(self) -> dict[str, object]:
        return {
            "requests": self.requests,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "reserved": self.reserved,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "token_unknown_requests": self.token_unknown_requests,
            "estimated_cost_usd": gateway.format_usd(self.estimated_cost_usd),
            "cost_unknown_requests": self.cost_unknown_requests,
            "committed_usd": gateway.format_usd(self.committed_usd),
        }


def _usage_aggregates() -> list[ColumnElement[Any]]:
    """Per-group report columns, in :class:`_Totals` field order.

    "Unknown" counts every record whose provider usage or cost is NULL, whatever
    its billability: a missing number is never reported as zero. Committed spend
    is the separate :func:`gateway.committed_amount` rule.
    """
    record = AiUsageRecord
    usd = Numeric(14, 6)
    return [
        func.count(),
        _count_where(record.status == UsageStatus.SUCCEEDED.value),
        _count_where(record.status == UsageStatus.FAILED.value),
        _count_where(record.status == UsageStatus.CANCELLED.value),
        _count_where(record.status == UsageStatus.RESERVED.value),
        func.coalesce(func.sum(record.input_tokens), 0),
        func.coalesce(func.sum(record.output_tokens), 0),
        _count_where(or_(record.input_tokens.is_(None), record.output_tokens.is_(None))),
        func.coalesce(func.sum(cast(record.cost_usd, usd)), 0),
        _count_where(record.cost_usd.is_(None)),
        func.coalesce(func.sum(cast(gateway.committed_amount(), usd)), 0),
    ]


def _totals_from_row(values: Sequence[Any]) -> _Totals:
    (
        requests,
        succeeded,
        failed,
        cancelled,
        reserved,
        input_tokens,
        output_tokens,
        token_unknown,
        cost,
        cost_unknown,
        committed,
    ) = values
    return _Totals(
        requests=int(requests),
        succeeded=int(succeeded),
        failed=int(failed),
        cancelled=int(cancelled),
        reserved=int(reserved),
        input_tokens=int(input_tokens),
        output_tokens=int(output_tokens),
        token_unknown_requests=int(token_unknown),
        estimated_cost_usd=Decimal(str(cost)),
        cost_unknown_requests=int(cost_unknown),
        committed_usd=Decimal(str(committed)),
    )


async def usage_report(db: AsyncSession, year: int, month: int) -> AiUsageReport:
    """Month totals and breakdowns from one SQL ``GROUP BY``; no record is loaded.

    Rows are grouped by (provider, model, UTC day): at most pairs x 31 groups,
    rolled up here into totals, per-pair and per-day figures.
    """
    start, end = gateway.month_bounds(year, month)
    day = gateway.utc_day(AiUsageRecord.started_at)
    groups = await db.execute(
        select(AiUsageRecord.provider, AiUsageRecord.model, day, *_usage_aggregates())
        .where(AiUsageRecord.started_at >= start, AiUsageRecord.started_at < end)
        .group_by(AiUsageRecord.provider, AiUsageRecord.model, day)
    )
    totals = _Totals()
    by_pair: dict[tuple[str, str], _Totals] = defaultdict(_Totals)
    by_day: dict[date, _Totals] = defaultdict(_Totals)
    for provider, model, group_day, *values in groups.all():
        group = _totals_from_row(values)
        totals.add(group)
        by_pair[(provider, model)].add(group)
        by_day[group_day].add(group)

    policy = await gateway.read_policy(db)
    budget = policy.monthly_budget_usd
    committed = gateway.format_usd(totals.committed_usd)
    remaining = None
    if budget is not None:
        remaining = gateway.format_usd(Decimal(budget) - totals.committed_usd)
    return AiUsageReport.model_validate(
        {
            "period": AiUsagePeriod(
                month=f"{year:04d}-{month:02d}", start=start, end=end, timezone="UTC"
            ),
            "actions_in_scope": [action.value for action in gateway.ACTIONS_IN_SCOPE],
            "guarantee": "local_estimate_only",
            "totals": AiUsageTotals.model_validate(totals.fields()),
            "budget": AiUsageBudget(
                monthly_budget_usd=_budget_str(budget),
                committed_usd=committed or "0.000000",
                remaining_usd=remaining,
            ),
            "by_provider_model": [
                AiUsageByProviderModel.model_validate(
                    {"provider": provider, "model": model, **pair.fields()}
                )
                for (provider, model), pair in sorted(by_pair.items())
            ],
            "by_day": [
                AiUsageByDay.model_validate({"date": day, **day_totals.fields()})
                for day, day_totals in sorted(by_day.items())
            ],
        }
    )


class UsageCursorError(ValueError):
    """``before`` names no record in the requested month."""


def _record_item(row: AiUsageRecord, now: datetime) -> AiUsageRecordItem:
    started_at = gateway.as_utc(row.started_at)
    stale = (
        row.status == UsageStatus.RESERVED.value
        and started_at <= now - gateway.STALE_RESERVATION_AFTER
    )
    return AiUsageRecordItem.model_validate(
        {
            "id": row.id,
            "actor_label": row.actor_label,
            "action": row.action,
            "provider": row.provider,
            "model": row.model,
            "status": row.status,
            "stale": stale,
            "billable": row.billable,
            "started_at": started_at,
            "completed_at": gateway.as_utc(row.completed_at) if row.completed_at else None,
            "latency_ms": row.latency_ms,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "usage_source": row.usage_source,
            "reserved_usd": gateway.format_usd(row.reserved_usd),
            "cost_usd": gateway.format_usd(row.cost_usd),
            "cost_source": row.cost_source,
            "error_category": row.error_category,
            "retry_of": row.retry_of,
        }
    )


async def usage_records(
    db: AsyncSession,
    year: int,
    month: int,
    *,
    limit: int,
    before: uuid.UUID | None,
) -> AiUsageRecordPage:
    """Newest first, keyset-paginated on (started_at, id)."""
    start, end = gateway.month_bounds(year, month)
    query = select(AiUsageRecord).where(
        AiUsageRecord.started_at >= start, AiUsageRecord.started_at < end
    )
    if before is not None:
        cursor = await db.get(AiUsageRecord, before)
        if cursor is None or not start <= gateway.as_utc(cursor.started_at) < end:
            raise UsageCursorError("before must name a record in the requested month")
        query = query.where(
            or_(
                AiUsageRecord.started_at < cursor.started_at,
                and_(
                    AiUsageRecord.started_at == cursor.started_at,
                    AiUsageRecord.id < cursor.id,
                ),
            )
        )
    rows = (
        await db.scalars(
            query.order_by(AiUsageRecord.started_at.desc(), AiUsageRecord.id.desc()).limit(
                limit + 1
            )
        )
    ).all()
    now = datetime.now(UTC)
    page = rows[:limit]
    return AiUsageRecordPage(
        items=[_record_item(row, now) for row in page],
        next_before=page[-1].id if len(rows) > limit else None,
    )


# ── Usage policy and pricing (#17) ─────────────────────────────────────


def policy_out(policy: AiUsagePolicy) -> AiUsagePolicyOut:
    return AiUsagePolicyOut.model_validate(
        {
            "monthly_budget_usd": _budget_str(policy.monthly_budget_usd),
            "max_output_tokens": policy.max_output_tokens,
            "max_concurrent_requests": policy.max_concurrent_requests,
            "max_requests_per_minute": policy.max_requests_per_minute,
            "unpriced_model_policy": policy.unpriced_model_policy,
            "guarantee": "local_estimate_only",
            "updated_at": gateway.as_utc(policy.updated_at) if policy.updated_at else None,
        }
    )


async def get_usage_policy(db: AsyncSession) -> AiUsagePolicyOut:
    return policy_out(await gateway.read_policy(db))


async def update_usage_policy(db: AsyncSession, update: AiUsagePolicyUpdate) -> AiUsagePolicyOut:
    policy = await db.get(AiUsagePolicy, 1)
    if policy is None:
        policy = gateway.default_policy()
        db.add(policy)
    policy.monthly_budget_usd = (
        Decimal(update.monthly_budget_usd) if update.monthly_budget_usd is not None else None
    )
    policy.max_output_tokens = update.max_output_tokens
    policy.max_concurrent_requests = update.max_concurrent_requests
    policy.max_requests_per_minute = update.max_requests_per_minute
    policy.unpriced_model_policy = update.unpriced_model_policy
    policy.updated_at = datetime.now(UTC)
    await db.flush()
    return policy_out(policy)


def pricing_out(row: AiModelPricing) -> AiModelPricingOut:
    return AiModelPricingOut.model_validate(
        {
            "provider": row.provider,
            "model": row.model,
            "input_usd_per_mtok": _price_str(row.input_usd_per_mtok),
            "output_usd_per_mtok": _price_str(row.output_usd_per_mtok),
            "updated_at": gateway.as_utc(row.updated_at) if row.updated_at else None,
        }
    )


async def list_pricing(db: AsyncSession) -> AiModelPricingList:
    rows = (
        await db.scalars(
            select(AiModelPricing).order_by(AiModelPricing.provider, AiModelPricing.model)
        )
    ).all()
    return AiModelPricingList(items=[pricing_out(row) for row in rows])


async def get_pricing(
    db: AsyncSession, provider: AiProvider, model: str
) -> AiModelPricingOut | None:
    row = await db.get(AiModelPricing, (provider.value, model))
    return pricing_out(row) if row is not None else None


async def set_pricing(
    db: AsyncSession, provider: AiProvider, model: str, update: AiModelPricingUpdate
) -> AiModelPricingOut:
    row = await db.get(AiModelPricing, (provider.value, model))
    if row is None:
        row = AiModelPricing(provider=provider.value, model=model)
        db.add(row)
    row.input_usd_per_mtok = Decimal(update.input_usd_per_mtok)
    row.output_usd_per_mtok = Decimal(update.output_usd_per_mtok)
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return pricing_out(row)


async def delete_pricing(db: AsyncSession, provider: AiProvider, model: str) -> bool:
    result = await db.execute(
        delete(AiModelPricing).where(
            AiModelPricing.provider == provider.value, AiModelPricing.model == model
        )
    )
    await db.flush()
    return getattr(result, "rowcount", 0) == 1
