import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import Base
from app.core.uuidv7 import uuid7

_JSON = JSONB().with_variant(JSON, "sqlite")


class GarbaInventory(Base):
    """Admin-set seat cap for one category on one event date. ``sold`` rises on payment."""

    __tablename__ = "garba_inventory"

    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    event_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "category IN ('men', 'women', 'couple')",
            name="ck_garba_inventory_category",
        ),
        CheckConstraint(
            "event_date IN ('17', '18')",
            name="ck_garba_inventory_date",
        ),
        CheckConstraint("capacity >= 0", name="ck_garba_inventory_capacity"),
        CheckConstraint("sold >= 0", name="ck_garba_inventory_sold"),
    )


class GarbaTicket(Base):
    """One entry pass. The QR code encodes ``qr_token`` and nothing else."""

    __tablename__ = "garba_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garba_bookings.id"), nullable=False
    )
    ticket_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    attendee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    attendee_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    qr_token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_garba_tickets_booking", "booking_id"),)


class GarbaCategoryLock(Base):
    """One row per category. Writers lock it so capacity and ticket numbers stay exact."""

    __tablename__ = "garba_category_locks"

    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    next_ticket_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class GarbaBooking(Base):
    __tablename__ = "garba_bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    dates: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    razorpay_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ticket_numbers: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('men', 'women', 'couple')",
            name="ck_garba_bookings_category",
        ),
        CheckConstraint(
            "dates IN ('17', '18', 'both')",
            name="ck_garba_bookings_dates",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PAID', 'EXPIRED')",
            name="ck_garba_bookings_status",
        ),
        CheckConstraint("quantity >= 1", name="ck_garba_bookings_quantity"),
        CheckConstraint(
            "(category = 'couple' AND quantity <= 2) OR "
            "(category IN ('men', 'women') AND quantity <= 4)",
            name="ck_garba_bookings_max_quantity",
        ),
        CheckConstraint("amount > 0", name="ck_garba_bookings_amount"),
        CheckConstraint("currency = 'INR'", name="ck_garba_bookings_currency"),
        Index("idx_garba_bookings_customer", "customer_profile_id"),
        Index("idx_garba_bookings_category_status", "category", "status"),
    )
