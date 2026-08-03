import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch
    from app.cart.models import CartItem
    from app.inventory.models import InventoryItem
    from app.order.models import OrderItem


class Menu(Base, TimestampMixin):
    __tablename__ = "menus"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Main Menu")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    branch: Mapped["Branch"] = relationship("Branch", back_populates="menus")
    categories: Mapped[list["MenuCategory"]] = relationship(
        "MenuCategory", back_populates="menu"
    )


class MenuCategory(Base, TimestampMixin):
    __tablename__ = "menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    menu_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menus.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    menu: Mapped["Menu"] = relationship("Menu", back_populates="categories")
    items: Mapped[list["MenuItem"]] = relationship(
        "MenuItem", back_populates="category"
    )


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_veg: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    category: Mapped["MenuCategory"] = relationship(
        "MenuCategory", back_populates="items"
    )
    modifiers: Mapped[list["MenuModifier"]] = relationship(
        "MenuModifier", back_populates="menu_item"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="menu_item"
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="menu_item"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="menu_item"
    )

    __table_args__ = (
        CheckConstraint(
            "base_price >= 0", name="ck_menu_items_base_price_non_negative"
        ),
        Index("idx_menu_items_category_avail", category_id, is_available),
    )


class MenuModifier(Base):
    __tablename__ = "menu_modifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_delta: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.00
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
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="modifiers")
