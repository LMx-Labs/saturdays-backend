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
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch
    from app.menu.models import MenuItem


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    branch: Mapped["Branch"] = relationship("Branch", back_populates="inventory_items")
    menu_item: Mapped["MenuItem"] = relationship(
        "MenuItem", back_populates="inventory_items"
    )
    logs: Mapped[list["InventoryLog"]] = relationship(
        "InventoryLog", back_populates="inventory_item"
    )

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0", name="ck_inventory_items_quantity_non_negative"
        ),
        UniqueConstraint("branch_id", "menu_item_id", name="uix_inventory_branch_item"),
        Index("idx_inventory_branch_item", branch_id, menu_item_id),
    )


class InventoryLog(Base):
    __tablename__ = "inventory_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False
    )
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    new_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="logs"
    )
