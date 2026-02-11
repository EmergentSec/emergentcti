"""add alerting and webhooks tables

Revision ID: 009
Revises: 008
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create alert_rules table
    op.create_table(
        "alert_rules",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        # Match conditions
        sa.Column("match_type", sa.String(64), nullable=True),
        sa.Column("match_value_pattern", sa.String(1024), nullable=True),
        sa.Column(
            "match_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("match_tlp", sa.String(16), nullable=True),
        sa.Column("match_confidence_min", sa.Integer(), nullable=True),
        sa.Column("match_feed_id", sa.Uuid(), nullable=True),
        # Notification config
        sa.Column(
            "notification_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "cooldown_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        # Timestamps
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
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_alert_rule_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_feed_id"],
            ["feeds.id"],
            name="fk_alert_rule_match_feed",
            ondelete="SET NULL",
        ),
    )

    # Create alert_events table
    op.create_table(
        "alert_events",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "notification_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notification_error", sa.Text(), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["alert_rules.id"],
            name="fk_alert_event_rule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_alert_event_observable",
            ondelete="CASCADE",
        ),
    )

    # Create indexes on alert_events
    op.create_index(
        "ix_alert_event_rule_id", "alert_events", ["rule_id"]
    )
    op.create_index(
        "ix_alert_event_observable_id", "alert_events", ["observable_id"]
    )
    op.create_index(
        "ix_alert_event_triggered_at", "alert_events", ["triggered_at"]
    )

    # Create webhook_configs table
    op.create_table(
        "webhook_configs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_webhook_config_created_by",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("webhook_configs")
    op.drop_index("ix_alert_event_triggered_at", table_name="alert_events")
    op.drop_index("ix_alert_event_observable_id", table_name="alert_events")
    op.drop_index("ix_alert_event_rule_id", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
