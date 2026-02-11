"""Feed default confidence values.

Revision ID: 014
Revises: 013
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    feed_defaults = [
        ("AbuseIPDB", 90),
        ("OpenPhish", 80),
        ("URLhaus", 75),
        ("Emerging Threats", 70),
        ("Blocklist.de", 65),
        ("Tor Exit Nodes", 30),
    ]
    for name, confidence in feed_defaults:
        op.execute(
            sa.text(
                "UPDATE feeds SET config = COALESCE(config, '{}'::jsonb) || (:patch)::jsonb "
                "WHERE name = :name"
            ).bindparams(
                name=name,
                patch=json.dumps({"default_confidence": confidence}),
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE feeds SET config = config - 'default_confidence' "
            "WHERE config ? 'default_confidence'"
        )
    )
