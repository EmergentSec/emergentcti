"""add audit_logs table

Revision ID: 011
Revises: 010
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_log_user",
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_audit_log_entity", "audit_logs", ["entity_type", "entity_id"]
    )
    op.create_index(
        "ix_audit_log_created_at", "audit_logs", ["created_at"]
    )
    op.create_index(
        "ix_audit_log_user_id", "audit_logs", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_log_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_log_entity", table_name="audit_logs")
    op.drop_table("audit_logs")
