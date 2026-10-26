"""Forward-only production order reservation and retry identity.

Revision ID: dg_20261026_01
Revises: 0006
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "dg_20261026_01"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "timezone_name",
            sa.String(64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
    )
    op.add_column("orders", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column(
        "orders", sa.Column("request_fingerprint", sa.String(64), nullable=True)
    )
    op.create_index(
        "uq_orders_customer_idempotency",
        "orders",
        ["customer_profile_id", "idempotency_key"],
        unique=True,
    )
    op.create_table(
        "order_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "quantity > 0", name="ck_order_reservations_quantity_positive"
        ),
    )
    op.create_index(
        "uq_order_reservation_item",
        "order_reservations",
        ["order_id", "inventory_item_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_order_reservation_item", table_name="order_reservations")
    op.drop_table("order_reservations")
    op.drop_index("uq_orders_customer_idempotency", table_name="orders")
    op.drop_column("orders", "request_fingerprint")
    op.drop_column("orders", "idempotency_key")
    op.drop_column("branches", "timezone_name")
