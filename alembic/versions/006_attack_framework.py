"""MITRE ATT&CK framework tables - tactics, techniques, and observable mappings

Revision ID: 006
Revises: 005
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- attack_tactics ---
    op.create_table(
        "attack_tactics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id", sa.String(16), nullable=False
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column(
            "short_name",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        "ix_attack_tactic_external_id",
        "attack_tactics",
        ["external_id"],
    )
    op.create_index(
        "ix_attack_tactic_order",
        "attack_tactics",
        ["order"],
    )

    # --- attack_techniques ---
    op.create_table(
        "attack_techniques",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id", sa.String(32), nullable=False
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_subtechnique",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["attack_techniques.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_attack_technique_external_id",
        "attack_techniques",
        ["external_id"],
    )
    op.create_index(
        "ix_attack_technique_parent_id",
        "attack_techniques",
        ["parent_id"],
    )

    # --- attack_technique_tactics (junction) ---
    op.create_table(
        "attack_technique_tactics",
        sa.Column(
            "technique_id", sa.Uuid(), nullable=False
        ),
        sa.Column("tactic_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("technique_id", "tactic_id"),
        sa.ForeignKeyConstraint(
            ["technique_id"],
            ["attack_techniques.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tactic_id"],
            ["attack_tactics.id"],
            ondelete="CASCADE",
        ),
    )

    # --- observable_attack_techniques ---
    op.create_table(
        "observable_attack_techniques",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "observable_id", sa.Uuid(), nullable=False
        ),
        sa.Column(
            "technique_id", sa.Uuid(), nullable=False
        ),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observable_id",
            "technique_id",
            name="uq_observable_technique",
        ),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technique_id"],
            ["attack_techniques.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_obs_technique_observable_id",
        "observable_attack_techniques",
        ["observable_id"],
    )
    op.create_index(
        "ix_obs_technique_technique_id",
        "observable_attack_techniques",
        ["technique_id"],
    )


def downgrade() -> None:
    op.drop_table("observable_attack_techniques")
    op.drop_table("attack_technique_tactics")
    op.drop_table("attack_techniques")
    op.drop_table("attack_tactics")
