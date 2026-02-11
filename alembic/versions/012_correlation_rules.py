"""add correlation_rules and correlation_events tables

Revision ID: 012
Revises: 011
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- correlation_rules --
    op.create_table(
        "correlation_rules",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        # Match conditions
        sa.Column("match_type", sa.String(64), nullable=True),
        sa.Column("match_value_pattern", sa.String(512), nullable=True),
        sa.Column(
            "match_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("match_tlp", sa.String(32), nullable=True),
        sa.Column("match_confidence_min", sa.Integer(), nullable=True),
        sa.Column("match_feed_id", sa.Uuid(), nullable=True),
        # Action fields
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("target_threat_actor_id", sa.Uuid(), nullable=True),
        sa.Column("target_campaign_id", sa.Uuid(), nullable=True),
        sa.Column("target_technique_id", sa.Uuid(), nullable=True),
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
            name="fk_correlation_rule_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_feed_id"],
            ["feeds.id"],
            name="fk_correlation_rule_feed",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_threat_actor_id"],
            ["threat_actors.id"],
            name="fk_correlation_rule_threat_actor",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_campaign_id"],
            ["campaigns.id"],
            name="fk_correlation_rule_campaign",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_technique_id"],
            ["attack_techniques.id"],
            name="fk_correlation_rule_technique",
            ondelete="SET NULL",
        ),
    )

    # -- correlation_events --
    op.create_table(
        "correlation_events",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "correlated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(32), nullable=False),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["correlation_rules.id"],
            name="fk_correlation_event_rule",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_correlation_event_observable",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_correlation_event_rule_id",
        "correlation_events",
        ["rule_id"],
    )
    op.create_index(
        "ix_correlation_event_observable_id",
        "correlation_events",
        ["observable_id"],
    )
    op.create_index(
        "ix_correlation_event_correlated_at",
        "correlation_events",
        ["correlated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_correlation_event_correlated_at", table_name="correlation_events")
    op.drop_index("ix_correlation_event_observable_id", table_name="correlation_events")
    op.drop_index("ix_correlation_event_rule_id", table_name="correlation_events")
    op.drop_table("correlation_events")
    op.drop_table("correlation_rules")
