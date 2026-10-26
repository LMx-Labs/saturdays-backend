"""Persist immutable order pricing details for new orders.

Revision ID: dg_20261026_03
Revises: dg_20261026_02
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "dg_20261026_03"
down_revision = "dg_20261026_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable for legacy orders whose historic fee/tax policy cannot be inferred.
    op.add_column(
        "orders",
        sa.Column("price_breakdown_snapshot", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "price_breakdown_snapshot")
