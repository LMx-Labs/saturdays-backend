import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.merchant.models import Merchant
    from app.branch.models import Branch


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    banner_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cuisine_types: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(255)), nullable=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="brands")
    branches: Mapped[list["Branch"]] = relationship("Branch", back_populates="brand")

    __table_args__ = (
        Index("idx_brands_merchant_id", merchant_id, postgresql_where=(TimestampMixin.deleted_at == None)),
    )
