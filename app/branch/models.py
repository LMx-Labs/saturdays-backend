import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.brand.models import Brand
    from app.cart.models import Cart
    from app.coupon.models import Coupon
    from app.customer.models import CustomerFavorite
    from app.inventory.models import InventoryItem
    from app.kitchen.models import Kitchen
    from app.menu.models import Menu
    from app.order.models import Order
    from app.review.models import Review


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address_text: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    opening_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(8, 0, 0)
    )
    closing_time: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(23, 0, 0)
    )

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="branches")
    kitchens: Mapped[list["Kitchen"]] = relationship("Kitchen", back_populates="branch")
    menus: Mapped[list["Menu"]] = relationship("Menu", back_populates="branch")
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="branch"
    )
    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="branch")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="branch")
    coupons: Mapped[list["Coupon"]] = relationship("Coupon", back_populates="branch")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="branch")
    favorites: Mapped[list["CustomerFavorite"]] = relationship(
        "CustomerFavorite", back_populates="branch"
    )

    __table_args__ = (
        Index(
            "idx_branches_brand_id",
            brand_id,
            postgresql_where=(TimestampMixin.deleted_at == None),
        ),
    )
