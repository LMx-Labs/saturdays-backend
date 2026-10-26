"""Persist review visibility used by protected review APIs.

Revision ID: dg_20261026_05
Revises: dg_20261026_04
"""

import sqlalchemy as sa

from alembic import op

revision = "dg_20261026_05"
down_revision = "dg_20261026_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("reviews", "is_hidden")
