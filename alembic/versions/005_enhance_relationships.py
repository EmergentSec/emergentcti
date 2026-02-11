"""enhance observable_relationships with created_by, unique constraint, and indexes

Revision ID: 005
Revises: 003
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add created_by column (nullable FK to users.id)
    op.add_column(
        "observable_relationships",
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # Add unique constraint on (source_id, target_id, relationship_type)
    op.create_unique_constraint(
        "uq_relationship_src_tgt_type",
        "observable_relationships",
        ["source_id", "target_id", "relationship_type"],
    )

    # Add indexes for efficient lookups
    op.create_index(
        "ix_relationship_source_id",
        "observable_relationships",
        ["source_id"],
    )
    op.create_index(
        "ix_relationship_target_id",
        "observable_relationships",
        ["target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_relationship_target_id", table_name="observable_relationships")
    op.drop_index("ix_relationship_source_id", table_name="observable_relationships")
    op.drop_constraint(
        "uq_relationship_src_tgt_type", "observable_relationships", type_="unique"
    )
    op.drop_column("observable_relationships", "created_by")
