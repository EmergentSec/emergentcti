"""add AI provider settings

Revision ID: 006
Revises: 005
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("credentials_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("key_hint", sa.String(8), nullable=True),
        sa.Column("model_cache", sa.JSON(), nullable=True),
        sa.Column("models_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("last_check_status", sa.String(16), nullable=True),
        sa.Column("last_check_category", sa.String(32), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("provider"),
        sa.CheckConstraint(
            "provider IN ('anthropic', 'openai', 'openrouter', 'xai')",
            name="ck_ai_providers_provider",
        ),
        sa.CheckConstraint(
            "last_check_status IS NULL OR last_check_status IN ('ok', 'error')",
            name="ck_ai_providers_last_check_status",
        ),
        sa.CheckConstraint(
            "last_check_category IS NULL OR last_check_category IN "
            "('invalid_credentials', 'permission_denied', 'rate_limited', "
            "'insufficient_quota', 'model_unavailable', 'timeout', 'network_error', "
            "'provider_error', 'not_configured')",
            name="ck_ai_providers_last_check_category",
        ),
    )

    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_provider", sa.String(32), nullable=True),
        sa.Column("default_model", sa.String(255), nullable=True),
        sa.Column(
            "default_model_is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["default_provider"],
            ["ai_providers.provider"],
            name="fk_ai_settings_default_provider",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("id = 1", name="ck_ai_settings_singleton"),
        sa.CheckConstraint(
            "(default_provider IS NULL AND default_model IS NULL) OR "
            "(default_provider IS NOT NULL AND default_model IS NOT NULL)",
            name="ck_ai_settings_default_pair",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_settings")
    op.drop_table("ai_providers")
