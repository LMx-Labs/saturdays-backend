import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.merchant.models import Merchant
    from app.order.models import Order


class MerchantSubscription(Base, TimestampMixin):
    __tablename__ = "merchant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    plan_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="BASIC")
    billing_cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MONTHLY"
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    commission_rate_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=5.00
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(
        "Merchant", back_populates="subscriptions"
    )


class PlatformCommission(Base):
    __tablename__ = "platform_commissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    gross_order_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    commission_rate_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    commission_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    merchant_net_payout: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="commissions")
    merchant: Mapped["Merchant"] = relationship(
        "Merchant", back_populates="commissions"
    )
