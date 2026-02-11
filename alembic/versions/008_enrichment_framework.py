"""add enrichment framework tables

Revision ID: 008
Revises: 007
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enrichmentrunstatus enum
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'enrichmentrunstatus'
            ) THEN
                CREATE TYPE enrichmentrunstatus AS ENUM (
                    'pending', 'running', 'success', 'failure'
                );
            END IF;
        END $$;
        """
    )

    # Create enrichment_configs table
    op.create_table(
        "enrichment_configs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "auto_enrich",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "priority", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("provider_name", name="uq_enrichment_config_provider"),
    )

    # Create enrichment_runs table
    op.create_table(
        "enrichment_runs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "success",
                "failure",
                name="enrichmentrunstatus",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "result_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_enrichment_run_observable",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            ["users.id"],
            name="fk_enrichment_run_user",
            ondelete="SET NULL",
        ),
    )

    # Create indexes on enrichment_runs
    op.create_index(
        "ix_enrichment_run_obs_provider",
        "enrichment_runs",
        ["observable_id", "provider_name"],
    )
    op.create_index(
        "ix_enrichment_run_created_at",
        "enrichment_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_enrichment_run_created_at", table_name="enrichment_runs")
    op.drop_index("ix_enrichment_run_obs_provider", table_name="enrichment_runs")
    op.drop_table("enrichment_runs")
    op.drop_table("enrichment_configs")
    op.execute("DROP TYPE IF EXISTS enrichmentrunstatus")
