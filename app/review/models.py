import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch
    from app.customer.models import CustomerProfile
    from app.order.models import Order


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True
    )
    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_profiles.id"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="review")
    customer_profile: Mapped["CustomerProfile"] = relationship(
        "CustomerProfile", back_populates="reviews"
    )
    branch: Mapped["Branch"] = relationship("Branch", back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_1_to_5"),
    )
