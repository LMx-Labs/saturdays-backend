import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.auth.models import User
    from app.branch.models import Branch
    from app.coupon.models import CouponRedemption
    from app.customer.models import CustomerProfile
    from app.menu.models import MenuItem
    from app.payment.models import Payment
    from app.review.models import Review
    from app.subscription.models import PlatformCommission


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Portion of total_amount paid with brand store credit instead of money.
    store_credit_applied: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PLACED")
    delivery_address_snapshot: Mapped[Any] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=False
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

    # Relationships
    customer_profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="orders"
    )
    branch: Mapped["Branch"] = relationship("Branch", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order")
    status_logs: Mapped[list["OrderStatusLog"]] = relationship(
        "OrderStatusLog", back_populates="order"
    )
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order")
    coupon_redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="order"
    )
    review: Mapped[Optional["Review"]] = relationship(
        "Review", back_populates="order", uselist=False
    )
    commissions: Mapped[list["PlatformCommission"]] = relationship(
        "PlatformCommission", back_populates="order"
    )

    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0", name="ck_orders_total_amount_non_negative"
        ),
        CheckConstraint(
            "store_credit_applied >= 0 AND store_credit_applied <= total_amount",
            name="ck_orders_store_credit_range",
        ),
        Index("idx_orders_branch_status", branch_id, status, created_at.desc()),
        Index("idx_orders_customer", customer_profile_id, created_at.desc()),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False
    )
    item_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_price_snapshot: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_modifiers_snapshot: Mapped[Any | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship(
        "MenuItem", back_populates="order_items"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )


class OrderStatusLog(Base):
    __tablename__ = "order_status_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="status_logs")
    changed_by_user: Mapped["User"] = relationship("User")
