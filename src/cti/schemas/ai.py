# ruff: noqa: TC001, TC003
from __future__ import annotations

import enum
import re
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from cti.models.ai import AiProvider


class ModelSource(enum.StrEnum):
    LIVE = "live"
    CACHE = "cache"
    FALLBACK = "fallback"


class AiErrorCategory(enum.StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    INSUFFICIENT_QUOTA = "insufficient_quota"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PROVIDER_ERROR = "provider_error"
    NOT_CONFIGURED = "not_configured"
    # Local guardrails (#17). They never occur on ``check`` and are deliberately
    # absent from ``ck_ai_providers_last_check_category``.
    BUDGET_EXCEEDED = "budget_exceeded"
    CONCURRENCY_LIMIT = "concurrency_limit"
    LOCAL_RATE_LIMITED = "local_rate_limited"
    MODEL_BLOCKED_UNPRICED = "model_blocked_unpriced"
    SHARING_FORBIDDEN = "sharing_forbidden"
    SHARING_NOT_APPROVED = "sharing_not_approved"


class AiModel(BaseModel):
    id: str
    name: str
    context_length: int | None = None


class AiError(BaseModel):
    category: AiErrorCategory
    message: str


class AiProviderStatus(BaseModel):
    provider: AiProvider
    display_name: str
    configured: bool
    key_hint: str | None
    models_fetched_at: datetime | None
    last_check_status: Literal["ok", "error"] | None
    last_check_category: AiErrorCategory | None
    last_checked_at: datetime | None
    setup_url: str


class AiDefault(BaseModel):
    provider: AiProvider
    model: str
    is_custom: bool


class AiSettings(BaseModel):
    providers: list[AiProviderStatus]
    default: AiDefault | None


class AiModelList(BaseModel):
    provider: AiProvider
    source: ModelSource
    fetched_at: datetime | None
    models: list[AiModel]
    error: AiError | None


class AiCheckResult(BaseModel):
    ok: bool
    error: AiError | None
    checked_at: datetime


UsageSourceName = Literal["provider_reported", "unknown"]
CostSourceName = Literal["estimated", "unknown"]
UsageStatusName = Literal["reserved", "succeeded", "failed", "cancelled"]
BillableName = Literal["no", "yes", "unknown"]


class AiUsageSummary(BaseModel):
    """Accounting for one request. ``None`` means unknown, never zero."""

    record_id: uuid.UUID
    input_tokens: int | None
    output_tokens: int | None
    usage_source: UsageSourceName
    cost_usd: str | None
    cost_source: CostSourceName


class AiInferenceResult(BaseModel):
    ok: bool
    error: AiError | None
    latency_ms: int | None
    usage: AiUsageSummary | None = None


class AiProviderKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_and_validate_key(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if not value.isascii():
            raise ValueError("API key must contain only ASCII characters")
        if any(unicodedata.category(character) == "Cc" for character in value):
            raise ValueError("API key must not contain control characters")
        value = value.strip()
        if not value:
            raise ValueError("API key must not be empty")
        return value


def _validate_model_id(value: str) -> str:
    if not value.strip():
        raise ValueError("Model ID must not be empty or whitespace-only")
    if len(value) > 255:
        raise ValueError("Model ID must be at most 255 characters")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Model ID must not contain control characters")
    return value


class AiDefaultUpdate(BaseModel):
    provider: AiProvider
    model: str
    is_custom: bool

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _validate_model_id(value)


class AiInferenceTestRequest(BaseModel):
    model: str
    confirm: Literal[True]
    #: Client-supplied id of the failed attempt being retried. Informational only.
    retry_of: uuid.UUID | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _validate_model_id(value)

    @field_validator("confirm", mode="before")
    @classmethod
    def validate_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("Explicit confirmation is required")
        return value


# ── Usage accounting and guardrails (#17) ─────────────────────────────


_MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_MAX_BUDGET = Decimal("99999999.9999")  # Numeric(12, 4)
_MAX_PRICE = Decimal("999999.999999")  # Numeric(12, 6)


#: Accepted accounting periods. The upper bound stops at 9999-11 because a
#: period's exclusive end (the next month's first instant) must be a datetime.
_FIRST_MONTH = (2000, 1)
_LAST_MONTH = (9999, 11)


def parse_month(value: str) -> tuple[int, int]:
    match = _MONTH_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("month must be YYYY-MM")
    period = int(match.group(1)), int(match.group(2))
    if not _FIRST_MONTH <= period <= _LAST_MONTH:
        raise ValueError("month must be between 2000-01 and 9999-11")
    return period


def _decimal(value: object, *, places: int, maximum: Decimal, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation:
        raise ValueError(f"{field} must be a decimal string") from None
    if not parsed.is_finite() or parsed < 0 or parsed > maximum:
        raise ValueError(f"{field} must be between 0 and {maximum}")
    exponent = parsed.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -places:
        raise ValueError(f"{field} allows at most {places} decimal places")
    return parsed


class AiInferencePreview(BaseModel):
    provider: AiProvider
    model: str
    action: Literal["inference_test"]
    content: str
    max_output_tokens: int
    pricing_known: bool
    estimated_max_cost_usd: str | None
    policy_decision: Literal["allowed", "blocked_unpriced", "over_budget"]
    destination_note: str


class AiUsagePeriod(BaseModel):
    month: str
    start: datetime
    end: datetime
    timezone: Literal["UTC"]


class AiUsageTotals(BaseModel):
    requests: int
    succeeded: int
    failed: int
    cancelled: int
    reserved: int
    input_tokens: int
    output_tokens: int
    token_unknown_requests: int
    estimated_cost_usd: str
    cost_unknown_requests: int
    committed_usd: str


class AiUsageBudget(BaseModel):
    monthly_budget_usd: str | None
    committed_usd: str
    remaining_usd: str | None


class AiUsageByProviderModel(AiUsageTotals):
    provider: str
    model: str


class AiUsageByDay(AiUsageTotals):
    date: date


class AiUsageReport(BaseModel):
    period: AiUsagePeriod
    actions_in_scope: list[str]
    guarantee: Literal["local_estimate_only"]
    totals: AiUsageTotals
    budget: AiUsageBudget
    by_provider_model: list[AiUsageByProviderModel]
    # The breakdown holds at most ``by_provider_model_limit`` groups (most
    # requests first); every group beyond it is summed into ``..._other``.
    by_provider_model_limit: int
    by_provider_model_omitted_groups: int
    by_provider_model_other: AiUsageTotals | None
    by_day: list[AiUsageByDay]


class AiUsageRecordItem(BaseModel):
    id: uuid.UUID
    actor_label: str | None
    action: str
    provider: str
    model: str
    status: UsageStatusName
    stale: bool
    billable: BillableName
    started_at: datetime
    completed_at: datetime | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    usage_source: UsageSourceName
    reserved_usd: str | None
    cost_usd: str | None
    cost_source: CostSourceName
    error_category: str | None
    retry_of: uuid.UUID | None


class AiUsageRecordPage(BaseModel):
    items: list[AiUsageRecordItem]
    next_before: uuid.UUID | None


class AiUsagePolicyOut(BaseModel):
    monthly_budget_usd: str | None
    max_output_tokens: int
    max_concurrent_requests: int
    max_requests_per_minute: int
    unpriced_model_policy: Literal["block", "permit"]
    guarantee: Literal["local_estimate_only"]
    updated_at: datetime | None


class AiUsagePolicyUpdate(BaseModel):
    """Full replacement. A null budget means no budget."""

    monthly_budget_usd: str | None
    max_output_tokens: int = Field(ge=1, le=32000)
    max_concurrent_requests: int = Field(ge=1, le=50)
    max_requests_per_minute: int = Field(ge=1, le=600)
    unpriced_model_policy: Literal["block", "permit"]

    @field_validator("monthly_budget_usd", mode="before")
    @classmethod
    def validate_budget(cls, value: object) -> object:
        if value is None:
            return None
        return str(_decimal(value, places=4, maximum=_MAX_BUDGET, field="monthly_budget_usd"))


class AiModelPricingOut(BaseModel):
    provider: AiProvider
    model: str
    input_usd_per_mtok: str
    output_usd_per_mtok: str
    updated_at: datetime | None


class AiModelPricingList(BaseModel):
    items: list[AiModelPricingOut]


class AiModelPricingUpdate(BaseModel):
    input_usd_per_mtok: str
    output_usd_per_mtok: str

    @field_validator("input_usd_per_mtok", "output_usd_per_mtok", mode="before")
    @classmethod
    def validate_price(cls, value: object) -> object:
        return str(_decimal(value, places=6, maximum=_MAX_PRICE, field="price"))


def validate_model_id(value: str) -> str:
    return _validate_model_id(value)
