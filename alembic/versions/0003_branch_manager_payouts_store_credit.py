"""branch_id on users, store credit, merchant payouts

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_TS = dict(server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade() -> None:
    # --- BranchManager <-> branch link -------------------------------------
    op.add_column(
        "users",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_branch_id", "users", "branches", ["branch_id"], ["id"]
    )
    op.create_index("idx_users_branch_id", "users", ["branch_id"])

    # --- store credit applied on an order ----------------------------------
    op.add_column(
        "orders",
        sa.Column(
            "store_credit_applied",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_orders_store_credit_range",
        "orders",
        "store_credit_applied >= 0 AND store_credit_applied <= total_amount",
    )

    # --- store credit ------------------------------------------------------
    op.create_table(
        "store_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id"),
            nullable=False,
        ),
        sa.Column(
            "source_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("initial_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("balance", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.CheckConstraint("initial_amount > 0", name="ck_store_credits_initial_positive"),
        sa.CheckConstraint(
            "balance >= 0 AND balance <= initial_amount",
            name="ck_store_credits_balance_range",
        ),
    )
    op.create_index(
        "idx_store_credits_customer_brand",
        "store_credits",
        ["customer_profile_id", "brand_id"],
    )
    op.create_table(
        "store_credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "credit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("store_credits.id"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
    )
    op.create_index(
        "idx_store_credit_tx_credit", "store_credit_transactions", ["credit_id"]
    )

    # --- payouts -----------------------------------------------------------
    op.create_table(
        "merchant_payout_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("razorpay_contact_id", sa.String(100), nullable=False),
        sa.Column("razorpay_fund_account_id", sa.String(100), nullable=False),
        sa.Column("account_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
    )
    op.create_table(
        "payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
        ),
        sa.Column("payout_date", sa.Date(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("razorpay_payout_id", sa.String(100), nullable=True),
        sa.Column("utr", sa.String(50), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **_TS),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_TS),
        sa.UniqueConstraint("merchant_id", "payout_date", name="uq_payouts_merchant_date"),
        sa.UniqueConstraint("idempotency_key", name="uq_payouts_idempotency_key"),
        sa.CheckConstraint("net_amount > 0", name="ck_payouts_net_positive"),
    )
    op.create_index("idx_payouts_status", "payouts", ["status"])
    op.create_index("idx_payouts_razorpay_id", "payouts", ["razorpay_payout_id"])
    op.create_table(
        "payout_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payout_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payouts.id"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("gross_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("idx_payout_items_payout", "payout_items", ["payout_id"])


def downgrade() -> None:
    op.drop_table("payout_items")
    op.drop_table("payouts")
    op.drop_table("merchant_payout_accounts")
    op.drop_table("store_credit_transactions")
    op.drop_table("store_credits")
    op.drop_constraint("ck_orders_store_credit_range", "orders", type_="check")
    op.drop_column("orders", "store_credit_applied")
    op.drop_index("idx_users_branch_id", table_name="users")
    op.drop_constraint("fk_users_branch_id", "users", type_="foreignkey")
    op.drop_column("users", "branch_id")
