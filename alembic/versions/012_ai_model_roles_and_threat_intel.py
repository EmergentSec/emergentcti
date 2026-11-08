"""add AI research/writer model roles and threat-intel actions

Revision ID: 012
Revises: 011
Create Date: 2026-11-08

Adds research and writer model slots on ``ai_settings`` (alongside the
existing default), and expands ``ai_usage_records.action`` to include
``threat_research`` and ``report_write``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

_ACTIONS = "'inference_test', 'threat_research', 'report_write'"


def upgrade() -> None:
    with op.batch_alter_table("ai_settings") as batch:
        batch.add_column(sa.Column("research_provider", sa.String(32), nullable=True))
        batch.add_column(sa.Column("research_model", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column(
                "research_model_is_custom",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("writer_provider", sa.String(32), nullable=True))
        batch.add_column(sa.Column("writer_model", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column(
                "writer_model_is_custom",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.create_foreign_key(
            "fk_ai_settings_research_provider",
            "ai_providers",
            ["research_provider"],
            ["provider"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_ai_settings_writer_provider",
            "ai_providers",
            ["writer_provider"],
            ["provider"],
            ondelete="SET NULL",
        )
        batch.create_check_constraint(
            "ck_ai_settings_research_pair",
            "research_provider IS NULL OR research_model IS NOT NULL",
        )
        batch.create_check_constraint(
            "ck_ai_settings_writer_pair",
            "writer_provider IS NULL OR writer_model IS NOT NULL",
        )

    with op.batch_alter_table("ai_usage_records") as batch:
        batch.drop_constraint("ck_ai_usage_records_action", type_="check")
        batch.create_check_constraint(
            "ck_ai_usage_records_action",
            f"action IN ({_ACTIONS})",
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_usage_records") as batch:
        batch.drop_constraint("ck_ai_usage_records_action", type_="check")
        batch.create_check_constraint(
            "ck_ai_usage_records_action",
            "action IN ('inference_test')",
        )

    with op.batch_alter_table("ai_settings") as batch:
        batch.drop_constraint("ck_ai_settings_writer_pair", type_="check")
        batch.drop_constraint("ck_ai_settings_research_pair", type_="check")
        batch.drop_constraint("fk_ai_settings_writer_provider", type_="foreignkey")
        batch.drop_constraint("fk_ai_settings_research_provider", type_="foreignkey")
        batch.drop_column("writer_model_is_custom")
        batch.drop_column("writer_model")
        batch.drop_column("writer_provider")
        batch.drop_column("research_model_is_custom")
        batch.drop_column("research_model")
        batch.drop_column("research_provider")
