"""add analyst confidence floor and pinned override

Revision ID: 008
Revises: 007
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    with op.batch_alter_table("observables") as batch_op:
        batch_op.add_column(sa.Column("manual_confidence", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("confidence_override", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("override_set_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("override_set_by_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_observables_override_set_by_id",
            "users",
            ["override_set_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_observables_manual_confidence",
            "manual_confidence IS NULL OR (manual_confidence >= 0 AND manual_confidence <= 100)",
        )
        batch_op.create_check_constraint(
            "ck_observables_confidence_override",
            "confidence_override IS NULL OR "
            "(confidence_override >= 0 AND confidence_override <= 100)",
        )
        batch_op.create_check_constraint(
            "ck_observables_override_set_at",
            "confidence_override IS NOT NULL OR override_set_at IS NULL",
        )

    # Any confidence the feed sources don't explain was set by an analyst
    # (manual create, or a manual raise of a feed observable), and nothing
    # recorded it before this migration. Record it as the analyst floor so
    # the first recompute can never silently lower it. Rows without sources
    # are covered too: MAX over no rows is NULL, so they compare against -1.
    op.execute(
        sa.text(
            """
            UPDATE observables
            SET manual_confidence = confidence_score
            WHERE confidence_score > COALESCE(
                (
                    SELECT MAX(observable_sources.source_confidence)
                    FROM observable_sources
                    WHERE observable_sources.observable_id = observables.id
                ),
                -1
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("observables") as batch_op:
        batch_op.drop_constraint("ck_observables_override_set_at", type_="check")
        batch_op.drop_constraint("ck_observables_confidence_override", type_="check")
        batch_op.drop_constraint("ck_observables_manual_confidence", type_="check")
        batch_op.drop_constraint("fk_observables_override_set_by_id", type_="foreignkey")
        batch_op.drop_column("override_set_by_id")
        batch_op.drop_column("override_set_at")
        batch_op.drop_column("confidence_override")
        batch_op.drop_column("manual_confidence")
