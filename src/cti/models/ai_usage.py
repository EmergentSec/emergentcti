"""AI usage accounting and spending guardrails (issue #17).

Binding contract: ``docs/superpowers/specs/2026-11-02-ai-usage-guardrails.md``.

``ai_usage_records`` is accounting metadata only. It never holds prompts,
responses, provider error bodies or credentials. Unknown token counts and
costs are ``NULL``, never ``0``. Rows are written only by
:mod:`cti.services.ai.gateway`.
"""

# ruff: noqa: TC003
from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base


class AiAction(enum.StrEnum):
    """Actions that are accounted. Model listing and credential checks never are."""

    INFERENCE_TEST = "inference_test"
    THREAT_RESEARCH = "threat_research"
    REPORT_WRITE = "report_write"


class UsageStatus(enum.StrEnum):
    RESERVED = "reserved"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Billable(enum.StrEnum):
    NO = "no"
    YES = "yes"
    UNKNOWN = "unknown"


class UsageSource(enum.StrEnum):
    PROVIDER_REPORTED = "provider_reported"
    UNKNOWN = "unknown"


class CostSource(enum.StrEnum):
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class UnpricedModelPolicy(enum.StrEnum):
    BLOCK = "block"
    PERMIT = "permit"


def _in_list(column: str, values: type[enum.StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


def _utcnow() -> datetime:
    return datetime.now(UTC)


#: Defaults written by migration 011 and used when the singleton is missing.
DEFAULT_MAX_OUTPUT_TOKENS = 1024
DEFAULT_MAX_CONCURRENT_REQUESTS = 2
DEFAULT_MAX_REQUESTS_PER_MINUTE = 10


class AiUsagePolicy(Base):
    __tablename__ = "ai_usage_policy"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ai_usage_policy_singleton"),
        CheckConstraint(
            "monthly_budget_usd IS NULL OR monthly_budget_usd >= 0",
            name="ck_ai_usage_policy_budget",
        ),
        CheckConstraint(
            "max_output_tokens BETWEEN 1 AND 32000", name="ck_ai_usage_policy_max_output"
        ),
        CheckConstraint(
            "max_concurrent_requests BETWEEN 1 AND 50", name="ck_ai_usage_policy_concurrency"
        ),
        CheckConstraint(
            "max_requests_per_minute BETWEEN 1 AND 600", name="ck_ai_usage_policy_rate"
        ),
        CheckConstraint(
            _in_list("unpriced_model_policy", UnpricedModelPolicy),
            name="ck_ai_usage_policy_unpriced",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None)
    max_output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_OUTPUT_TOKENS
    )
    max_concurrent_requests: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_CONCURRENT_REQUESTS
    )
    max_requests_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_REQUESTS_PER_MINUTE
    )
    unpriced_model_policy: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UnpricedModelPolicy.BLOCK.value
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )


class AiModelPricing(Base):
    """Admin-entered prices. No built-in price table ships."""

    __tablename__ = "ai_model_pricing"
    __table_args__ = (
        CheckConstraint("input_usd_per_mtok >= 0", name="ck_ai_model_pricing_input"),
        CheckConstraint("output_usd_per_mtok >= 0", name="ck_ai_model_pricing_output"),
    )

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    model: Mapped[str] = mapped_column(String(255), primary_key=True)
    input_usd_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    output_usd_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )


class AiUsageRecord(Base):
    __tablename__ = "ai_usage_records"
    __table_args__ = (
        CheckConstraint(_in_list("action", AiAction), name="ck_ai_usage_records_action"),
        CheckConstraint(_in_list("status", UsageStatus), name="ck_ai_usage_records_status"),
        CheckConstraint(_in_list("billable", Billable), name="ck_ai_usage_records_billable"),
        CheckConstraint(
            _in_list("usage_source", UsageSource), name="ck_ai_usage_records_usage_source"
        ),
        CheckConstraint(
            _in_list("cost_source", CostSource), name="ck_ai_usage_records_cost_source"
        ),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) "
            "AND (output_tokens IS NULL OR output_tokens >= 0)",
            name="ck_ai_usage_records_tokens",
        ),
        Index("ix_ai_usage_records_started_at", "started_at"),
        Index("ix_ai_usage_records_provider_model", "provider", "model", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    billable: Mapped[str] = mapped_column(String(8), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_source: Mapped[str] = mapped_column(String(32), nullable=False)
    reserved_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    cost_source: Mapped[str] = mapped_column(String(16), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retry_of: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AiUsageRecord(id={self.id}, provider={self.provider!r}, "
            f"model={self.model!r}, status={self.status!r})>"
        )
