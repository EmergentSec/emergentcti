"""add threat actors and campaigns tables

Revision ID: 010
Revises: 009
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create threat_actors table
    op.create_table(
        "threat_actors",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("motivation", sa.String(128), nullable=True),
        sa.Column("sophistication", sa.String(64), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column(
            "tlp",
            sa.String(16),
            nullable=False,
            server_default="clear",
        ),
        sa.Column(
            "external_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            name="fk_threat_actor_created_by",
            ondelete="SET NULL",
        ),
    )

    op.create_index("ix_threat_actor_name", "threat_actors", ["name"])
    op.create_index("ix_threat_actor_country", "threat_actors", ["country"])

    # Create threat_actor_observables junction table
    op.create_table(
        "threat_actor_observables",
        sa.Column("threat_actor_id", sa.Uuid(), nullable=False),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("threat_actor_id", "observable_id"),
        sa.ForeignKeyConstraint(
            ["threat_actor_id"],
            ["threat_actors.id"],
            name="fk_ta_obs_threat_actor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_ta_obs_observable",
            ondelete="CASCADE",
        ),
    )

    # Create threat_actor_techniques junction table
    op.create_table(
        "threat_actor_techniques",
        sa.Column("threat_actor_id", sa.Uuid(), nullable=False),
        sa.Column("technique_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("threat_actor_id", "technique_id"),
        sa.ForeignKeyConstraint(
            ["threat_actor_id"],
            ["threat_actors.id"],
            name="fk_ta_tech_threat_actor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technique_id"],
            ["attack_techniques.id"],
            name="fk_ta_tech_technique",
            ondelete="CASCADE",
        ),
    )

    # Create campaigns table
    op.create_table(
        "campaigns",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("threat_actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="suspected",
        ),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column(
            "tlp",
            sa.String(16),
            nullable=False,
            server_default="clear",
        ),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column(
            "external_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            ["threat_actor_id"],
            ["threat_actors.id"],
            name="fk_campaign_threat_actor",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_campaign_created_by",
            ondelete="SET NULL",
        ),
    )

    op.create_index("ix_campaign_name", "campaigns", ["name"])
    op.create_index("ix_campaign_status", "campaigns", ["status"])
    op.create_index(
        "ix_campaign_threat_actor_id", "campaigns", ["threat_actor_id"]
    )

    # Create campaign_observables junction table
    op.create_table(
        "campaign_observables",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("campaign_id", "observable_id"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_camp_obs_campaign",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_camp_obs_observable",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("campaign_observables")
    op.drop_index("ix_campaign_threat_actor_id", table_name="campaigns")
    op.drop_index("ix_campaign_status", table_name="campaigns")
    op.drop_index("ix_campaign_name", table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_table("threat_actor_techniques")
    op.drop_table("threat_actor_observables")
    op.drop_index("ix_threat_actor_country", table_name="threat_actors")
    op.drop_index("ix_threat_actor_name", table_name="threat_actors")
    op.drop_table("threat_actors")
