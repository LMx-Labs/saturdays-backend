"""Track deliberate stock pauses separately from automatic exhaustion.

Revision ID: dg_20261026_04
Revises: dg_20261026_03
"""

import sqlalchemy as sa

from alembic import op

revision = "dg_20261026_04"
down_revision = "dg_20261026_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Legacy false flags cannot distinguish a manual pause from exhaustion.
    # Preserve safety until an owner explicitly resumes the item.
    op.execute("UPDATE inventory_items SET is_paused = TRUE WHERE is_in_stock = FALSE")


def downgrade() -> None:
    op.drop_column("inventory_items", "is_paused")
