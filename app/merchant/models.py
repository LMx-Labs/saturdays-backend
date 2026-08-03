import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.auth.models import User
    from app.brand.models import Brand
    from app.subscription.models import MerchantSubscription, PlatformCommission


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_entity_name: Mapped[str] = mapped_column(String(150), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fssai_license_number: Mapped[str] = mapped_column(String(30), nullable=False)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_ifsc_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")

    # Relationships
    owner_user: Mapped["User"] = relationship("User")
    brands: Mapped[list["Brand"]] = relationship("Brand", back_populates="merchant")
    subscriptions: Mapped[list["MerchantSubscription"]] = relationship(
        "MerchantSubscription", back_populates="merchant"
    )
    commissions: Mapped[list["PlatformCommission"]] = relationship(
        "PlatformCommission", back_populates="merchant"
    )
