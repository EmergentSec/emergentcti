"""add tags and enforced TLP markings

Revision ID: 009
Revises: 008
Create Date: 2026-11-01

Every new marking column is nullable and left NULL (Unspecified): nothing is
backfilled. Every existing export profile becomes ``internal``, which allows
Unspecified, so existing exports return exactly what they did before.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

# Frozen copy of the allowed values: migrations must not import app code.
_TLP_VALUES = "'clear', 'green', 'amber', 'amber+strict', 'red'"


def _tlp_check(column: str) -> str:
    return f"{column} IS NULL OR {column} IN ({_TLP_VALUES})"


def upgrade() -> None:
    with op.batch_alter_table("feeds") as batch_op:
        batch_op.add_column(sa.Column("tlp", sa.String(16), nullable=True))
        batch_op.create_check_constraint("ck_feeds_tlp", _tlp_check("tlp"))

    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("tlp", sa.String(16), nullable=True))
        batch_op.create_check_constraint("ck_reports_tlp", _tlp_check("tlp"))

    with op.batch_alter_table("observables") as batch_op:
        batch_op.add_column(sa.Column("manual_tlp", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("tlp_override", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("tlp_override_reason", sa.String(500), nullable=True))
        batch_op.add_column(
            sa.Column("tlp_override_set_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("tlp_override_set_by_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_observables_tlp_override_set_by_id",
            "users",
            ["tlp_override_set_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint("ck_observables_manual_tlp", _tlp_check("manual_tlp"))
        batch_op.create_check_constraint("ck_observables_tlp_override", _tlp_check("tlp_override"))
        batch_op.create_check_constraint(
            "ck_observables_tlp_override_fields",
            "(tlp_override IS NULL AND tlp_override_reason IS NULL "
            "AND tlp_override_set_at IS NULL) OR "
            "(tlp_override IS NOT NULL AND tlp_override_reason IS NOT NULL "
            "AND tlp_override_set_at IS NOT NULL)",
        )

    with op.batch_alter_table("export_profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "destination",
                sa.String(16),
                nullable=False,
                server_default="internal",
            )
        )
        batch_op.create_check_constraint(
            "ck_export_profile_destination",
            "destination IN ('internal', 'community', 'public')",
        )

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )
    op.create_table(
        "observable_tags",
        sa.Column("observable_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("observable_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["observable_id"],
            ["observables.id"],
            name="fk_observable_tags_observable_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_observable_tags_tag_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_observable_tags_tag_id", "observable_tags", ["tag_id"])
    op.create_table(
        "report_tags",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], name="fk_report_tags_report_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_report_tags_tag_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_report_tags_tag_id", "report_tags", ["tag_id"])
    op.create_table(
        "export_profile_tags",
        sa.Column("export_profile_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("export_profile_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["export_profile_id"],
            ["export_profiles.id"],
            name="fk_export_profile_tags_export_profile_id",
            ondelete="CASCADE",
        ),
        # RESTRICT: deleting a tag a profile filters on must never silently
        # broaden that profile.
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_export_profile_tags_tag_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_export_profile_tags_tag_id", "export_profile_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_export_profile_tags_tag_id", table_name="export_profile_tags")
    op.drop_table("export_profile_tags")
    op.drop_index("ix_report_tags_tag_id", table_name="report_tags")
    op.drop_table("report_tags")
    op.drop_index("ix_observable_tags_tag_id", table_name="observable_tags")
    op.drop_table("observable_tags")
    op.drop_table("tags")

    with op.batch_alter_table("export_profiles") as batch_op:
        batch_op.drop_constraint("ck_export_profile_destination", type_="check")
        batch_op.drop_column("destination")

    with op.batch_alter_table("observables") as batch_op:
        batch_op.drop_constraint("ck_observables_tlp_override_fields", type_="check")
        batch_op.drop_constraint("ck_observables_tlp_override", type_="check")
        batch_op.drop_constraint("ck_observables_manual_tlp", type_="check")
        batch_op.drop_constraint("fk_observables_tlp_override_set_by_id", type_="foreignkey")
        batch_op.drop_column("tlp_override_set_by_id")
        batch_op.drop_column("tlp_override_set_at")
        batch_op.drop_column("tlp_override_reason")
        batch_op.drop_column("tlp_override")
        batch_op.drop_column("manual_tlp")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_constraint("ck_reports_tlp", type_="check")
        batch_op.drop_column("tlp")

    with op.batch_alter_table("feeds") as batch_op:
        batch_op.drop_constraint("ck_feeds_tlp", type_="check")
        batch_op.drop_column("tlp")
