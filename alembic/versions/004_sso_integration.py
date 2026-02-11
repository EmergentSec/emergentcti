"""SSO integration - add auth_provider, external_id, avatar_url to users and
create sso_provider_configs table

Revision ID: 004
Revises: 003
Create Date: 2026-02-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the authprovider enum type via raw SQL (idempotent)
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE authprovider AS ENUM ('local', 'azure_ad', 'google', 'oidc'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    # Use PostgreSQL ENUM with create_type=False to reference existing type
    auth_provider_enum = postgresql.ENUM(
        "local", "azure_ad", "google", "oidc", name="authprovider", create_type=False
    )

    # Add new columns to users table
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            auth_provider_enum,
            nullable=False,
            server_default="local",
        ),
    )
    op.add_column(
        "users",
        sa.Column("external_id", sa.String(256), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(2048), nullable=True),
    )

    # Add unique constraint for provider + external_id combination
    op.create_unique_constraint(
        "uq_user_provider_external_id",
        "users",
        ["auth_provider", "external_id"],
    )

    # Create sso_provider_configs table
    op.create_table(
        "sso_provider_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_type",
            auth_provider_enum,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "provider_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("client_secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "default_role",
            postgresql.ENUM(
                "admin", "analyst", "readonly", name="userrole", create_type=False
            ),
            nullable=False,
            server_default="readonly",
        ),
        sa.Column("allowed_domains", postgresql.JSONB(), nullable=True),
        sa.Column(
            "auto_create_users",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_type"),
    )


def downgrade() -> None:
    op.drop_table("sso_provider_configs")
    op.drop_constraint("uq_user_provider_external_id", "users", type_="unique")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "external_id")
    op.drop_column("users", "auth_provider")
    op.execute("DROP TYPE IF EXISTS authprovider")
