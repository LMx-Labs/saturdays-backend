import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch
    from app.merchant.models import Merchant


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cuisine_types: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)).with_variant(JSON(), "sqlite"), nullable=True
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="brands")
    branches: Mapped[list["Branch"]] = relationship("Branch", back_populates="brand")

    __table_args__ = (
        Index(
            "idx_brands_merchant_id",
            merchant_id,
            postgresql_where=(TimestampMixin.deleted_at == None),
        ),
    )
