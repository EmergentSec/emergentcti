"""add native_confidence to observable_sources

Revision ID: 003
Revises: 002
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "observable_sources",
        sa.Column("native_confidence", sa.Integer(), nullable=False, server_default="50"),
    )
    # Backfill from the current (possibly already-decayed) value — best available origin.
    op.execute("UPDATE observable_sources SET native_confidence = source_confidence")


def downgrade() -> None:
    op.drop_column("observable_sources", "native_confidence")
