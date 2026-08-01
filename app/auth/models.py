import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.base_model import Base, TimestampMixin
from app.core.uuidv7 import uuid7

if TYPE_CHECKING:
    from app.customer.models import CustomerProfile
    from app.merchant.models import Merchant
    from app.order.models import OrderStatusLog
    from app.notification.models import Notification
    from app.admin.models import AdminAuditLog


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid7
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Customer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    customer_profile: Mapped[Optional["CustomerProfile"]] = relationship(
        "CustomerProfile", back_populates="user", uselist=False
    )
    merchants: Mapped[list["Merchant"]] = relationship("Merchant", back_populates="owner_user")
    order_status_logs: Mapped[list["OrderStatusLog"]] = relationship("OrderStatusLog", back_populates="changed_by_user")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")
    admin_audit_logs: Mapped[list["AdminAuditLog"]] = relationship("AdminAuditLog", back_populates="admin_user")

    __table_args__ = (
        Index(
            "idx_users_email_lower",
            func.lower(email),
            unique=True,
            postgresql_where=(deleted_at == None)
        ),
    )
