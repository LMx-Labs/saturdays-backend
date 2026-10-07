import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.brand.models import Brand
    from app.customer.models import CustomerProfile


class StoreCredit(Base):
    """Credit a customer can spend at one brand ("shop") instead of a cash refund.

    ``balance`` is the spendable remainder; every change is mirrored by an
    append-only ``StoreCreditTransaction`` row.
    """

    __tablename__ = "store_credits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False
    )
    # One credit per cancelled order -> issuing is idempotent. NULL for manual grants.
    source_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, unique=True
    )
    initial_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer_profile: Mapped["CustomerProfile"] = relationship("CustomerProfile")
    brand: Mapped["Brand"] = relationship("Brand")
    transactions: Mapped[list["StoreCreditTransaction"]] = relationship(
        "StoreCreditTransaction", back_populates="credit"
    )

    __table_args__ = (
        CheckConstraint("initial_amount > 0", name="ck_store_credits_initial_positive"),
        CheckConstraint(
            "balance >= 0 AND balance <= initial_amount",
            name="ck_store_credits_balance_range",
        ),
        Index("idx_store_credits_customer_brand", customer_profile_id, brand_id),
    )


class StoreCreditTransaction(Base):
    __tablename__ = "store_credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    credit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("store_credits.id"), nullable=False
    )
    # ISSUED | REDEEMED | RESTORED
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    credit: Mapped["StoreCredit"] = relationship(
        "StoreCredit", back_populates="transactions"
    )

    __table_args__ = (Index("idx_store_credit_tx_credit", credit_id),)
