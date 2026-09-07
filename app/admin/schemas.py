import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MerchantApprovalRequest(BaseModel):
    action: str = Field(..., description="'APPROVE' or 'REJECT'")
    reason: str | None = Field(None, max_length=500)


class MerchantAdminSummary(BaseModel):
    id: uuid.UUID
    business_name: str
    legal_entity_name: str
    status: str
    gstin_masked: str | None = None
    fssai_license_masked: str
    bank_account_masked: str | None = None
    created_at: datetime


class MerchantAdminPage(BaseModel):
    items: list[MerchantAdminSummary]
    page: int
    page_size: int
    total: int
    pages: int


class BannerCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    image_url: str = Field(..., min_length=1, max_length=255)
    target_url: str | None = Field(None, max_length=255)
    display_order: int = Field(0, ge=0)
    is_active: bool = True


class BannerUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=150)
    image_url: str | None = Field(None, min_length=1, max_length=255)
    target_url: str | None = Field(None, max_length=255)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


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
