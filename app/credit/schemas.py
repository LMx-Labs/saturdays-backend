import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StoreCreditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    source_order_id: uuid.UUID | None = None
    initial_amount: float
    balance: float
    currency: str
    reason: str
    expires_at: datetime
    created_at: datetime


class StoreCreditBalanceResponse(BaseModel):
    brand_id: uuid.UUID
    available_balance: float
    currency: str = "INR"


class StoreCreditGrantRequest(BaseModel):
    """Manual grant by a PlatformAdmin (support gestures, goodwill)."""

    customer_profile_id: uuid.UUID
    brand_id: uuid.UUID
    amount: float = Field(..., gt=0, le=100000)
    reason: str = Field(..., min_length=1, max_length=100)
