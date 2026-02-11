"""add lifecycle, enrichment rate limiting, and reports

Revision ID: 013
Revises: 012
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- Indicator lifecycle columns on observables --
    op.add_column("observables", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "observables",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index(
        "ix_observables_is_active", "observables", ["is_active"]
    )
    op.create_index(
        "ix_observables_expires_at",
        "observables",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )

    # -- Feed TTL --
    op.add_column("feeds", sa.Column("default_ttl_days", sa.Integer(), nullable=True))

    # -- Enrichment rate limiting --
    op.add_column(
        "enrichment_configs",
        sa.Column(
            "rate_limit_per_minute",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
    )

    # -- Reports table --
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "format",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'pdf'"),
        ),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("generated_by", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["generated_by"],
            ["users.id"],
            name="fk_report_user",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_reports_generated_by", "reports", ["generated_by"])
    op.create_index("ix_reports_status", "reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_index("ix_reports_generated_by", table_name="reports")
    op.drop_table("reports")

    op.drop_column("enrichment_configs", "rate_limit_per_minute")
    op.drop_column("feeds", "default_ttl_days")

    op.drop_index("ix_observables_expires_at", table_name="observables")
    op.drop_index("ix_observables_is_active", table_name="observables")
    op.drop_column("observables", "is_active")
    op.drop_column("observables", "expires_at")
