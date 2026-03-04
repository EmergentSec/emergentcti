"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

observable_type = postgresql.ENUM(
    "ip-addr", "domain-name", "url", "file-hash", "email-addr", "command-line",
    name="observabletype",
    create_type=False,
)

feed_type = postgresql.ENUM("api", "file", "scraper", name="feedtype", create_type=False)

feed_run_status = postgresql.ENUM(
    "running", "success", "failure", name="feedrunstatus", create_type=False
)


def upgrade() -> None:
    # Create enum types
    observable_type.create(op.get_bind(), checkfirst=True)
    feed_type.create(op.get_bind(), checkfirst=True)
    feed_run_status.create(op.get_bind(), checkfirst=True)

    # observables
    op.create_table(
        "observables",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("type", observable_type, nullable=False),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "value", name="uq_observable_type_value"),
    )
    op.create_index("ix_observable_type", "observables", ["type"])
    op.create_index("ix_observable_value", "observables", ["value"])
    op.create_index("ix_observable_confidence", "observables", ["confidence_score"])
    op.create_index("ix_observable_last_seen", "observables", ["last_seen"])
    op.create_index(
        "ix_observable_type_confidence_lastseen",
        "observables",
        ["type", "confidence_score", "last_seen"],
    )

    # feeds
    op.create_table(
        "feeds",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(256), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feed_type", feed_type, nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("schedule_cron", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_preconfigured", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("auth_config_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("default_confidence", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # feed_runs
    op.create_table(
        "feed_runs",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", feed_run_status, nullable=False, server_default="running"),
        sa.Column("observables_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observables_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_feed_run_feed_id", "feed_runs", ["feed_id"])
    op.create_index("ix_feed_run_started", "feed_runs", ["started_at"])

    # observable_sources
    op.create_table(
        "observable_sources",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("source_confidence", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "first_seen_by_feed", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_by_feed", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["observable_id"], ["observables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("observable_id", "feed_id", name="uq_observable_source"),
    )
    op.create_index("ix_obs_source_feed", "observable_sources", ["feed_id"])
    op.create_index("ix_obs_source_observable", "observable_sources", ["observable_id"])

    # api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("observable_sources")
    op.drop_table("feed_runs")
    op.drop_table("feeds")
    op.drop_table("observables")

    op.execute("DROP TYPE IF EXISTS feedrunstatus")
    op.execute("DROP TYPE IF EXISTS feedtype")
    op.execute("DROP TYPE IF EXISTS observabletype")
