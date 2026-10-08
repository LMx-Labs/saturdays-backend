import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class MerchantApprovalRequest(BaseModel):
    action: str = Field(..., description="'APPROVE' or 'REJECT'")
    reason: str | None = Field(None, max_length=500)


class BannerCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    image_url: str = Field(..., min_length=1, max_length=255)
    target_url: str | None = Field(None, max_length=255)
    display_order: int = Field(0, ge=0)
    is_active: bool = True


class BannerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    image_url: str
    target_url: str | None = None
    display_order: int
    is_active: bool
    created_at: datetime


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    value: str | None = None


class FeatureFlagResponse(BaseModel):
    flag_key: str
    enabled: bool
    value: str | None = None


class RefundOverrideRequest(BaseModel):
    payment_id: uuid.UUID
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)


class RefundOverrideResponse(BaseModel):
    refund_transaction_id: str
    payment_id: uuid.UUID
    amount: float
    status: str
    reason: str
    processed_at: datetime


class AdminAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_user_id: uuid.UUID
    action: str
    target_entity: str
    target_entity_id: uuid.UUID | None = None
    changes_payload: Any
    ip_address: str
    created_at: datetime


class PlatformAnalyticsOverview(BaseModel):
    total_merchants: int
    active_merchants: int
    total_orders: int
    gross_revenue: float
    platform_commissions: float
    total_customers: int


class BranchManagerCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    branch_id: uuid.UUID


class BranchManagerAssignRequest(BaseModel):
    branch_id: uuid.UUID


class BranchManagerResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    branch_id: uuid.UUID
    branch_name: str
    brand_id: uuid.UUID


class AdminSetPasswordRequest(BaseModel):
    """Schema for administrator setting a user's password."""

    user_id: uuid.UUID | None = Field(default=None, description="Target user UUID")
    email: EmailStr | None = Field(default=None, description="Target user email")
    password: str | None = Field(
        default=None, min_length=8, max_length=128, description="New plaintext password"
    )
    new_password: str | None = Field(
        default=None, min_length=8, max_length=128, description="Alternative field for new password"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("password") and data.get("new_password"):
                data["password"] = data["new_password"]
        return data

    @model_validator(mode="after")
    def validate_password_presence(self) -> "AdminSetPasswordRequest":
        if not self.password:
            raise ValueError(
                "password (or new_password) is required and must be at least 8 characters."
            )
        return self


class AdminSetPasswordResponse(BaseModel):
    """Response schema for administrator setting password."""

    message: str = "Password has been successfully updated by administrator."
    user_id: uuid.UUID
    email: str

