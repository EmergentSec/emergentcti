"""add AI usage accounting and spending guardrails

Revision ID: 011
Revises: 010
Create Date: 2026-11-02

``ai_usage_policy`` is a singleton (``id = 1``) created here with defaults:
no budget, 1024 max output tokens, 2 concurrent requests, 10 requests per
minute, and unpriced models blocked. ``ai_model_pricing`` starts empty: prices
are admin-entered only. ``ai_usage_records`` holds accounting metadata only,
never prompts or responses; unknown tokens and costs stay NULL.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Frozen copies of the allowed values: migrations must not import app code.
_ACTIONS = "'inference_test'"
_STATUSES = "'reserved', 'succeeded', 'failed', 'cancelled'"
_BILLABLE = "'no', 'yes', 'unknown'"
_USAGE_SOURCES = "'provider_reported', 'unknown'"
_COST_SOURCES = "'estimated', 'unknown'"
_UNPRICED = "'block', 'permit'"


def upgrade() -> None:
    policy = op.create_table(
        "ai_usage_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monthly_budget_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("max_concurrent_requests", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("max_requests_per_minute", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("unpriced_model_policy", sa.String(16), nullable=False, server_default="block"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("id = 1", name="ck_ai_usage_policy_singleton"),
        sa.CheckConstraint(
            "monthly_budget_usd IS NULL OR monthly_budget_usd >= 0",
            name="ck_ai_usage_policy_budget",
        ),
        sa.CheckConstraint(
            "max_output_tokens BETWEEN 1 AND 32000", name="ck_ai_usage_policy_max_output"
        ),
        sa.CheckConstraint(
            "max_concurrent_requests BETWEEN 1 AND 50", name="ck_ai_usage_policy_concurrency"
        ),
        sa.CheckConstraint(
            "max_requests_per_minute BETWEEN 1 AND 600", name="ck_ai_usage_policy_rate"
        ),
        sa.CheckConstraint(
            f"unpriced_model_policy IN ({_UNPRICED})", name="ck_ai_usage_policy_unpriced"
        ),
    )
    op.bulk_insert(policy, [{"id": 1}])

    op.create_table(
        "ai_model_pricing",
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("model", sa.String(255), primary_key=True),
        sa.Column("input_usd_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_usd_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("input_usd_per_mtok >= 0", name="ck_ai_model_pricing_input"),
        sa.CheckConstraint("output_usd_per_mtok >= 0", name="ck_ai_model_pricing_output"),
    )

    op.create_table(
        "ai_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_label", sa.String(255), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("billable", sa.String(8), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_source", sa.String(32), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(14, 6), nullable=True),
        sa.Column("cost_usd", sa.Numeric(14, 6), nullable=True),
        sa.Column("cost_source", sa.String(16), nullable=False),
        sa.Column("error_category", sa.String(32), nullable=True),
        sa.Column("retry_of", sa.Uuid(), nullable=True),
        sa.CheckConstraint(f"action IN ({_ACTIONS})", name="ck_ai_usage_records_action"),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_ai_usage_records_status"),
        sa.CheckConstraint(f"billable IN ({_BILLABLE})", name="ck_ai_usage_records_billable"),
        sa.CheckConstraint(
            f"usage_source IN ({_USAGE_SOURCES})", name="ck_ai_usage_records_usage_source"
        ),
        sa.CheckConstraint(
            f"cost_source IN ({_COST_SOURCES})", name="ck_ai_usage_records_cost_source"
        ),
        sa.CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) "
            "AND (output_tokens IS NULL OR output_tokens >= 0)",
            name="ck_ai_usage_records_tokens",
        ),
    )
    op.create_index("ix_ai_usage_records_started_at", "ai_usage_records", ["started_at"])
    op.create_index(
        "ix_ai_usage_records_provider_model",
        "ai_usage_records",
        ["provider", "model", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_records_provider_model", table_name="ai_usage_records")
    op.drop_index("ix_ai_usage_records_started_at", table_name="ai_usage_records")
    op.drop_table("ai_usage_records")
    op.drop_table("ai_model_pricing")
    op.drop_table("ai_usage_policy")
