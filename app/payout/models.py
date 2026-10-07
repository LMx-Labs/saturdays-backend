import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.merchant.models import Merchant
    from app.order.models import Order

# Payout lifecycle
PAYOUT_PENDING = "PENDING"  # created, not (successfully) submitted to Razorpay yet
PAYOUT_PROCESSING = "PROCESSING"  # accepted by Razorpay (queued/pending/processing)
PAYOUT_PROCESSED = "PROCESSED"  # money reached the merchant (UTR available)
PAYOUT_FAILED = "FAILED"  # failed / rejected / reversed; retryable


class MerchantPayoutAccount(Base):
    """Razorpay contact + bank fund account created from a merchant's bank details."""

    __tablename__ = "merchant_payout_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, unique=True
    )
    razorpay_contact_id: Mapped[str] = mapped_column(String(100), nullable=False)
    razorpay_fund_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # sha256(account|ifsc): detects bank detail changes without storing them twice.
    account_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    merchant: Mapped["Merchant"] = relationship("Merchant")


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    commission_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PAYOUT_PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Sent as X-Payout-Idempotency; changes only after a definitive failure.
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    razorpay_payout_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    merchant: Mapped["Merchant"] = relationship("Merchant")
    items: Mapped[list["PayoutItem"]] = relationship(
        "PayoutItem", back_populates="payout"
    )

    __table_args__ = (
        UniqueConstraint("merchant_id", "payout_date", name="uq_payouts_merchant_date"),
        UniqueConstraint("idempotency_key", name="uq_payouts_idempotency_key"),
        CheckConstraint("net_amount > 0", name="ck_payouts_net_positive"),
        Index("idx_payouts_status", status),
        Index("idx_payouts_razorpay_id", razorpay_payout_id),
    )


class PayoutItem(Base):
    """One settled order inside a payout. ``order_id`` is unique: an order is paid once."""

    __tablename__ = "payout_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    payout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payouts.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True
    )
    gross_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    commission_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    payout: Mapped["Payout"] = relationship("Payout", back_populates="items")
    order: Mapped["Order"] = relationship("Order")

    __table_args__ = (Index("idx_payout_items_payout", payout_id),)
