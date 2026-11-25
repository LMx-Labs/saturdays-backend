"""Add Razorpay subscription fields, plan config, webhook events, and settlements tables.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- merchant_subscriptions: add new columns ---
    op.add_column(
        "merchant_subscriptions",
        sa.Column("razorpay_subscription_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("razorpay_payment_link_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("registration_fee_paid", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("registration_fee_payment_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("max_orders_per_day", sa.Integer(), nullable=False, server_default="40"),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("settlement_cycle_days", sa.Integer(), nullable=False, server_default="1"),
    )

    # --- subscription_plan_config ---
    op.create_table(
        "subscription_plan_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tier", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_monthly", sa.Integer(), nullable=False),
        sa.Column("max_orders_per_day", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("max_branches", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("commission_rate_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("features", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("offer_text", sa.String(255), nullable=True),
        sa.Column("razorpay_plan_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- razorpay_webhook_events ---
    op.create_table(
        "razorpay_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # --- merchant_settlements ---
    op.create_table(
        "merchant_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("settlement_id", sa.String(100), nullable=True),
        sa.Column("gross_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_deducted", sa.Numeric(10, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_merchant_settlements_merchant_id", "merchant_settlements", ["merchant_id"])
    op.create_index("ix_merchant_settlements_status", "merchant_settlements", ["status"])


def downgrade() -> None:
    op.drop_table("merchant_settlements")
    op.drop_table("razorpay_webhook_events")
    op.drop_table("subscription_plan_config")

    op.drop_column("merchant_subscriptions", "settlement_cycle_days")
    op.drop_column("merchant_subscriptions", "max_orders_per_day")
    op.drop_column("merchant_subscriptions", "trial_ends_at")
    op.drop_column("merchant_subscriptions", "is_trial")
    op.drop_column("merchant_subscriptions", "registration_fee_payment_id")
    op.drop_column("merchant_subscriptions", "registration_fee_paid")
    op.drop_column("merchant_subscriptions", "razorpay_payment_link_id")
    op.drop_column("merchant_subscriptions", "razorpay_subscription_id")
