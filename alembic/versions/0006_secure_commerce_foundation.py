"""add secure checkout and payment persistence

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_coupon_redemption_order",
        "coupon_redemptions",
        ["coupon_id", "order_id"],
    )
    op.create_table(
        "checkout_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_address_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="INR", nullable=False),
        sa.Column("items_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("address_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"]),
        sa.ForeignKeyConstraint(["customer_profile_id"], ["customer_profiles.id"]),
        sa.ForeignKeyConstraint(["delivery_address_id"], ["customer_addresses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(
        "idx_checkout_quotes_customer",
        "checkout_quotes",
        ["customer_profile_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_checkout_quotes_expiry", "checkout_quotes", ["expires_at"])

    op.add_column(
        "orders", sa.Column("subtotal", sa.Numeric(10, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "orders",
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "orders", sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "orders", sa.Column("delivery_fee", sa.Numeric(10, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "orders", sa.Column("currency", sa.String(10), server_default="INR", nullable=False)
    )
    op.add_column(
        "orders", sa.Column("checkout_quote_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("orders", sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("orders", sa.Column("cancellation_reason", sa.String(500), nullable=True))
    op.create_foreign_key(
        "fk_orders_checkout_quote", "orders", "checkout_quotes", ["checkout_quote_id"], ["id"]
    )
    op.create_foreign_key("fk_orders_coupon", "orders", "coupons", ["coupon_id"], ["id"])
    op.create_unique_constraint("uq_orders_checkout_quote", "orders", ["checkout_quote_id"])
    op.create_foreign_key(
        "fk_checkout_quotes_order", "checkout_quotes", "orders", ["order_id"], ["id"]
    )

    op.create_table(
        "stock_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="RESERVED", nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="ck_stock_reservation_quantity"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id", "inventory_item_id", name="uq_stock_reservation_order_item"
        ),
    )

    op.add_column(
        "payments", sa.Column("provider", sa.String(30), server_default="mock", nullable=False)
    )
    op.add_column("payments", sa.Column("provider_order_id", sa.String(100), nullable=True))
    op.create_unique_constraint("uq_payments_provider_order", "payments", ["provider_order_id"])
    op.add_column(
        "payment_transactions", sa.Column("idempotency_key", sa.String(255), nullable=True)
    )
    op.create_unique_constraint(
        "uq_payment_transaction_idempotency", "payment_transactions", ["idempotency_key"]
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_webhook_event"),
    )


def downgrade() -> None:
    op.drop_table("payment_webhook_events")
    op.drop_constraint("uq_payment_transaction_idempotency", "payment_transactions", type_="unique")
    op.drop_column("payment_transactions", "idempotency_key")
    op.drop_constraint("uq_payments_provider_order", "payments", type_="unique")
    op.drop_column("payments", "provider_order_id")
    op.drop_column("payments", "provider")
    op.drop_table("stock_reservations")
    op.drop_constraint("fk_checkout_quotes_order", "checkout_quotes", type_="foreignkey")
    op.drop_constraint("uq_orders_checkout_quote", "orders", type_="unique")
    op.drop_constraint("fk_orders_coupon", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_checkout_quote", "orders", type_="foreignkey")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "coupon_id")
    op.drop_column("orders", "checkout_quote_id")
    op.drop_column("orders", "currency")
    op.drop_column("orders", "delivery_fee")
    op.drop_column("orders", "tax_amount")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "subtotal")
    op.drop_table("checkout_quotes")
    op.drop_constraint("uq_coupon_redemption_order", "coupon_redemptions", type_="unique")
