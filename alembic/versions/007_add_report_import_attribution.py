"""add report import attribution to report_observables

Revision ID: 007
Revises: 006
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # batch_alter_table issues plain ALTERs on PostgreSQL and rebuilds the
    # table on SQLite, which cannot add constraints in place.
    with op.batch_alter_table("report_observables") as batch_op:
        batch_op.add_column(sa.Column("imported_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("imported_by_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("analyst_confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_excerpt", sa.String(500), nullable=True))
        batch_op.create_foreign_key(
            "fk_report_observables_imported_by_id",
            "users",
            ["imported_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_report_observables_analyst_confidence",
            "analyst_confidence IS NULL OR (analyst_confidence >= 0 AND analyst_confidence <= 100)",
        )


def downgrade() -> None:
    with op.batch_alter_table("report_observables") as batch_op:
        batch_op.drop_constraint("ck_report_observables_analyst_confidence", type_="check")
        batch_op.drop_constraint("fk_report_observables_imported_by_id", type_="foreignkey")
        batch_op.drop_column("source_excerpt")
        batch_op.drop_column("analyst_confidence")
        batch_op.drop_column("imported_by_id")
        batch_op.drop_column("imported_at")
