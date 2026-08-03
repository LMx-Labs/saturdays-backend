import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.auth.models import User
    from app.branch.models import Branch
    from app.cart.models import Cart
    from app.coupon.models import CouponRedemption
    from app.order.models import Order
    from app.payment.models import Payment
    from app.review.models import Review


class CustomerProfile(Base, TimestampMixin):
    __tablename__ = "customer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        "CustomerAddress", back_populates="customer_profile"
    )
    favorites: Mapped[list["CustomerFavorite"]] = relationship(
        "CustomerFavorite", back_populates="customer_profile"
    )
    carts: Mapped[list["Cart"]] = relationship(
        "Cart", back_populates="customer_profile"
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="customer_profile"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="customer_profile"
    )
    coupon_redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="customer_profile"
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="customer_profile"
    )


class CustomerAddress(Base, TimestampMixin):
    __tablename__ = "customer_addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    address_line: Mapped[str] = mapped_column(String(255), nullable=False)
    building_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    campus_zone: Mapped[str] = mapped_column(String(100), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    customer_profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="addresses"
    )


class CustomerFavorite(Base):
    __tablename__ = "customer_favorites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    customer_profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="favorites"
    )
    branch: Mapped["Branch"] = relationship("Branch", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint(
            "customer_profile_id", "branch_id", name="uix_customer_branch_favorite"
        ),
    )
