import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    discount_type: str = Field(..., description="'PERCENTAGE' or 'FLAT'")
    discount_value: float = Field(..., gt=0)
    max_discount_amount: float | None = Field(None, gt=0)
    min_order_amount: float = Field(0.00, ge=0)
    max_redemptions_per_user: int = Field(1, ge=1)
    valid_from: datetime
    valid_until: datetime
    branch_id: uuid.UUID | None = Field(
        None, description="None for platform coupons, UUID for restaurant coupons"
    )
    is_active: bool = True


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID | None = None
    code: str
    discount_type: str
    discount_value: float
    max_discount_amount: float | None = None
    min_order_amount: float
    max_redemptions_per_user: int
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    is_platform_coupon: bool = False
    created_at: datetime
    updated_at: datetime


class CouponValidateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    order_amount: float = Field(..., gt=0)
    branch_id: uuid.UUID | None = None


class CouponValidateResponse(BaseModel):
    is_valid: bool
    coupon_id: uuid.UUID
    code: str
    discount_type: str
    discount_amount: float
    final_amount: float
    message: str | None = None
