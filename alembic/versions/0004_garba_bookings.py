"""garba night ticket bookings

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "garba_category_locks",
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("next_ticket_number", sa.Integer(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "garba_category_locks",
            sa.column("category", sa.String),
            sa.column("next_ticket_number", sa.Integer),
        ),
        [
            {"category": "men", "next_ticket_number": 1},
            {"category": "women", "next_ticket_number": 1},
            {"category": "couple", "next_ticket_number": 1},
        ],
    )
    op.create_table(
        "garba_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_profiles.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("dates", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("attendees", postgresql.JSONB(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("razorpay_order_id", sa.String(100), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(100), nullable=True),
        sa.Column("ticket_numbers", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "category IN ('men', 'women', 'couple')",
            name="ck_garba_bookings_category",
        ),
        sa.CheckConstraint(
            "dates IN ('17', '18', 'both')",
            name="ck_garba_bookings_dates",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'EXPIRED')",
            name="ck_garba_bookings_status",
        ),
        sa.CheckConstraint("quantity >= 1", name="ck_garba_bookings_quantity"),
        sa.CheckConstraint(
            "(category = 'couple' AND quantity <= 2) OR "
            "(category IN ('men', 'women') AND quantity <= 4)",
            name="ck_garba_bookings_max_quantity",
        ),
        sa.CheckConstraint("amount > 0", name="ck_garba_bookings_amount"),
        sa.CheckConstraint("currency = 'INR'", name="ck_garba_bookings_currency"),
    )
    op.create_index(
        "idx_garba_bookings_customer", "garba_bookings", ["customer_profile_id"]
    )
    op.create_index(
        "idx_garba_bookings_category_status",
        "garba_bookings",
        ["category", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_garba_bookings_category_status", table_name="garba_bookings")
    op.drop_index("idx_garba_bookings_customer", table_name="garba_bookings")
    op.drop_table("garba_bookings")
    op.drop_table("garba_category_locks")
