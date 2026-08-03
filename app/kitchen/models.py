import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.branch.models import Branch


class Kitchen(Base, TimestampMixin):
    __tablename__ = "kitchens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(150), nullable=False, default="Main Kitchen"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    branch: Mapped["Branch"] = relationship("Branch", back_populates="kitchens")

    __table_args__ = (
        Index(
            "idx_kitchens_branch_id",
            branch_id,
            postgresql_where=(TimestampMixin.deleted_at == None),
        ),
    )
