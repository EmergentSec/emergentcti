"""add description, external_references, and observable_notes

Revision ID: 003
Revises: 002
Create Date: 2026-02-08 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("observables", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "observables",
        sa.Column("external_references", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "observable_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "observable_id", sa.Uuid(),
            sa.ForeignKey("observables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observable_notes_observable_id", "observable_notes", ["observable_id"])


def downgrade() -> None:
    op.drop_index("ix_observable_notes_observable_id")
    op.drop_table("observable_notes")
    op.drop_column("observables", "external_references")
    op.drop_column("observables", "description")
