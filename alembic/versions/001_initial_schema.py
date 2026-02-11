"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("api_key", sa.String(64), nullable=True),
        sa.Column(
            "role",
            sa.Enum("admin", "analyst", "readonly", name="userrole"),
            nullable=False,
            server_default="readonly",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("api_key"),
    )

    # Tags table
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6b7280"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Feeds table
    op.create_table(
        "feeds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feed_type", sa.Enum("api", "taxii", "file", "scraper", name="feedtype"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auth_config_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Observables table
    op.create_table(
        "observables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "ip-addr", "domain-name", "url", "file-hash", "email-addr",
                "command-line", "user-agent", "certificate", "asn", "cidr",
                name="observabletype",
            ),
            nullable=False,
        ),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("tlp", sa.String(16), nullable=False, server_default="clear"),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "value", name="uq_observable_type_value"),
    )
    op.create_index("ix_observable_type", "observables", ["type"])
    op.create_index("ix_observable_value", "observables", ["value"])
    op.create_index("ix_observable_last_seen", "observables", ["last_seen"])

    # Observable relationships
    op.create_table(
        "observable_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("observables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("observables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Feed runs
    op.create_table(
        "feed_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), sa.ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failure", name="feedrunstatus"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("observables_ingested", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Association tables
    op.create_table(
        "observable_tags",
        sa.Column("observable_id", sa.Uuid(), sa.ForeignKey("observables.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Uuid(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "observable_sources",
        sa.Column("observable_id", sa.Uuid(), sa.ForeignKey("observables.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("feed_id", sa.Uuid(), sa.ForeignKey("feeds.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("observable_sources")
    op.drop_table("observable_tags")
    op.drop_table("feed_runs")
    op.drop_table("observable_relationships")
    op.drop_table("observables")
    op.drop_table("feeds")
    op.drop_table("tags")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS feedtype")
    op.execute("DROP TYPE IF EXISTS feedrunstatus")
    op.execute("DROP TYPE IF EXISTS observabletype")
