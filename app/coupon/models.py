import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch
    from app.customer.models import CustomerProfile
    from app.order.models import Order


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_discount_amount: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    min_order_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.00
    )
    max_redemptions_per_user: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    branch: Mapped[Optional["Branch"]] = relationship(
        "Branch", back_populates="coupons"
    )
    redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="coupon"
    )


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    coupon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    discount_amount_applied: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="redemptions")
    customer_profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="coupon_redemptions"
    )
    order: Mapped["Order"] = relationship("Order", back_populates="coupon_redemptions")
