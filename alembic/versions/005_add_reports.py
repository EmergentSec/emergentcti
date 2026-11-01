"""add reports library

Revision ID: 005
Revises: 004
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "content_format",
            sa.String(16),
            nullable=False,
            server_default="markdown",
        ),
        sa.Column(
            "is_ai_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("ai_provider", sa.String(255), nullable=True),
        sa.Column("ai_model", sa.String(255), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_reports_created_by_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("origin IN ('provider', 'internal')", name="ck_reports_origin"),
        sa.CheckConstraint(
            "content_format IN ('markdown', 'text')",
            name="ck_reports_content_format",
        ),
        sa.CheckConstraint(
            "is_ai_generated OR "
            "(ai_provider IS NULL AND ai_model IS NULL AND ai_generated_at IS NULL)",
            name="ck_reports_ai_provenance",
        ),
    )
    op.create_index("ix_reports_published_at", "reports", ["published_at"])
    op.create_index("ix_reports_origin", "reports", ["origin"])
    op.create_index("ix_reports_source_name", "reports", ["source_name"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])

    op.create_table(
        "report_attachments",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_report_attachments_report_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("report_id", name="uq_report_attachments_report_id"),
        sa.CheckConstraint("size_bytes > 0", name="ck_report_attachments_size_bytes"),
    )

    op.create_table(
        "report_observables",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("report_id", "observable_id"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            name="fk_report_observables_report_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_report_observables_observable_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_report_observables_observable_id",
        "report_observables",
        ["observable_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_observables_observable_id",
        table_name="report_observables",
    )
    op.drop_table("report_observables")
    op.drop_table("report_attachments")
    op.drop_index("ix_reports_created_at", table_name="reports")
    op.drop_index("ix_reports_source_name", table_name="reports")
    op.drop_index("ix_reports_origin", table_name="reports")
    op.drop_index("ix_reports_published_at", table_name="reports")
    op.drop_table("reports")
