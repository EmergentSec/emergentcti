"""add allowlist entries and saved export profiles

Revision ID: 004
Revises: 003
Create Date: 2026-10-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Reuse the enum created in 001; never (re)create or drop it here.
observable_type = postgresql.ENUM(
    "ip-addr", "domain-name", "url", "file-hash", "email-addr", "command-line",
    name="observabletype",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "allowlist_entries",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("observable_type", observable_type, nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "observable_type", "value", name="uq_allowlist_entry_policy"),
        sa.CheckConstraint(
            "kind IN ('exact', 'cidr', 'domain_suffix')", name="ck_allowlist_entry_kind"
        ),
    )

    op.create_table(
        "export_profiles",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("type", observable_type, nullable=True),
        sa.Column("confidence_min", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("max_age_days", sa.Integer(), nullable=True),
        sa.Column("feed_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_export_profiles_name"),
        # RESTRICT: a feed referenced by a profile cannot be deleted, so a
        # profile can never silently widen to "all feeds".
        sa.ForeignKeyConstraint(
            ["feed_id"], ["feeds.id"], name="fk_export_profiles_feed_id", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("format IN ('text', 'json')", name="ck_export_profile_format"),
        sa.CheckConstraint(
            "confidence_min >= 0 AND confidence_min <= 100",
            name="ck_export_profile_confidence_min",
        ),
        sa.CheckConstraint(
            "max_age_days IS NULL OR (max_age_days >= 1 AND max_age_days <= 36500)",
            name="ck_export_profile_max_age_days",
        ),
    )
    op.create_index("ix_export_profile_feed_id", "export_profiles", ["feed_id"])


def downgrade() -> None:
    op.drop_index("ix_export_profile_feed_id", table_name="export_profiles")
    op.drop_table("export_profiles")
    op.drop_table("allowlist_entries")
