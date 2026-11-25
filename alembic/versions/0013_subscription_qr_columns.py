"""Add registration_fee_qr_url, plan_payment_link, and plan_qr_url to merchant_subscriptions.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merchant_subscriptions",
        sa.Column("registration_fee_qr_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("plan_payment_link", sa.String(500), nullable=True),
    )
    op.add_column(
        "merchant_subscriptions",
        sa.Column("plan_qr_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("merchant_subscriptions", "plan_qr_url")
    op.drop_column("merchant_subscriptions", "plan_payment_link")
    op.drop_column("merchant_subscriptions", "registration_fee_qr_url")
