"""drop garba event tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20

"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_garba_tickets_booking", table_name="garba_tickets")
    op.drop_table("garba_tickets")
    op.drop_table("garba_inventory")
    op.drop_index("idx_garba_bookings_category_status", table_name="garba_bookings")
    op.drop_index("idx_garba_bookings_customer", table_name="garba_bookings")
    op.drop_table("garba_bookings")
    op.drop_table("garba_category_locks")


def downgrade() -> None:
    raise NotImplementedError("Garba tables are not restored.")
