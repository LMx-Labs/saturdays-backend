import uuid
from datetime import datetime, date as date_type
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, JSON, func
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

    # Razorpay subscription fields
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    razorpay_payment_link_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    registration_fee_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    registration_fee_payment_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    registration_fee_qr_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    plan_payment_link: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    plan_qr_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )
    is_trial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    max_orders_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    settlement_cycle_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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


class SubscriptionPlanConfig(Base, TimestampMixin):
    """Admin-editable plan configuration stored in DB (overrides hardcoded defaults)."""
    __tablename__ = "subscription_plan_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tier: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_monthly: Mapped[int] = mapped_column(Integer, nullable=False)
    max_orders_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    max_branches: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    commission_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    features: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    offer_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)


class RazorpayWebhookEvent(Base):
    """Idempotency table for Razorpay webhook events."""
    __tablename__ = "razorpay_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MerchantSettlement(Base):
    """Settlement record per merchant payout cycle."""
    __tablename__ = "merchant_settlements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    settlement_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    commission_deducted: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    settlement_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
