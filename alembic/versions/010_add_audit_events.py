"""add append-only audit events

Revision ID: 010
Revises: 009
Create Date: 2026-11-02

``audit_events`` has no foreign keys on purpose: deleting a user, API key,
report, or feed must not delete or null out the history that names it. Nothing
is backfilled; history starts when this revision is applied.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Frozen copies of the allowed values: migrations must not import app code.
_ACTOR_TYPES = "'user', 'api_key', 'system'"
_OUTCOMES = "'succeeded', 'failed', 'denied', 'initiated', 'completed', 'interrupted'"


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("actor_label", sa.String(255), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("resource_label", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.CheckConstraint(f"actor_type IN ({_ACTOR_TYPES})", name="ck_audit_events_actor_type"),
        sa.CheckConstraint(f"outcome IN ({_OUTCOMES})", name="ck_audit_events_outcome"),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_type", "actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"])


def downgrade() -> None:
    for name in (
        "ix_audit_events_outcome",
        "ix_audit_events_resource",
        "ix_audit_events_action",
        "ix_audit_events_actor",
        "ix_audit_events_occurred_at",
    ):
        op.drop_index(name, table_name="audit_events")
    op.drop_table("audit_events")
