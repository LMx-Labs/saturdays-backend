import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionCreateRequest(BaseModel):
    plan_tier: str = Field(
        "BASIC", description="'BASIC', 'PROFESSIONAL', or 'ENTERPRISE'"
    )
    billing_cycle: str = Field("MONTHLY", description="'MONTHLY' or 'ANNUAL'")


class SubscriptionRenewalRequest(BaseModel):
    plan_tier: str | None = Field(None, description="Optional tier change upon renewal")
    duration_months: int = Field(
        1, ge=1, le=24, description="Renewal duration in months"
    )


class MerchantSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    plan_tier: str
    billing_cycle: str
    status: str
    commission_rate_percentage: float
    max_branches: int
    valid_until: datetime
    created_at: datetime
    updated_at: datetime


class PlatformCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    merchant_id: uuid.UUID
    gross_order_amount: float
    commission_rate_percentage: float
    commission_amount: float
    merchant_net_payout: float
    created_at: datetime


class SubscriptionInvoiceResponse(BaseModel):
    invoice_number: str
    merchant_id: uuid.UUID
    subscription_id: uuid.UUID
    plan_tier: str
    amount: float
    billing_cycle: str
    valid_until: datetime
    issued_at: datetime
