"""garba inventory caps and entry tickets

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-13

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_DEFAULTS = (
    ("men", "17", 35),
    ("men", "18", 35),
    ("women", "17", 55),
    ("women", "18", 55),
    ("couple", "17", 30),
    ("couple", "18", 30),
)


def upgrade() -> None:
    op.create_table(
        "garba_inventory",
        sa.Column("category", sa.String(20), primary_key=True),
        sa.Column("event_date", sa.String(10), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("sold", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "category IN ('men', 'women', 'couple')",
            name="ck_garba_inventory_category",
        ),
        sa.CheckConstraint(
            "event_date IN ('17', '18')",
            name="ck_garba_inventory_date",
        ),
        sa.CheckConstraint("capacity >= 0", name="ck_garba_inventory_capacity"),
        sa.CheckConstraint("sold >= 0", name="ck_garba_inventory_sold"),
    )
    op.bulk_insert(
        sa.table(
            "garba_inventory",
            sa.column("category", sa.String),
            sa.column("event_date", sa.String),
            sa.column("capacity", sa.Integer),
            sa.column("sold", sa.Integer),
        ),
        [
            {
                "category": category,
                "event_date": event_date,
                "capacity": capacity,
                "sold": 0,
            }
            for category, event_date, capacity in _DEFAULTS
        ],
    )
    op.create_table(
        "garba_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("garba_bookings.id"),
            nullable=False,
        ),
        sa.Column("ticket_number", sa.String(40), nullable=False, unique=True),
        sa.Column("attendee_name", sa.String(100), nullable=False),
        sa.Column("attendee_phone", sa.String(20), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("qr_token", sa.String(80), nullable=False, unique=True),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_garba_tickets_booking", "garba_tickets", ["booking_id"])


def downgrade() -> None:
    op.drop_index("idx_garba_tickets_booking", table_name="garba_tickets")
    op.drop_table("garba_tickets")
    op.drop_table("garba_inventory")
