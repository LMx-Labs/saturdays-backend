import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PayoutItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    gross_amount: float
    commission_amount: float
    net_amount: float


class PayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    payout_date: date
    gross_amount: float
    commission_amount: float
    net_amount: float
    currency: str
    status: str
    attempts: int
    razorpay_payout_id: str | None = None
    utr: str | None = None
    failure_reason: str | None = None
    processed_at: datetime | None = None
    created_at: datetime


class PayoutDetailResponse(PayoutResponse):
    items: list[PayoutItemResponse] = []


class PayoutRunRequest(BaseModel):
    payout_date: date | None = Field(
        None, description="Settlement date (defaults to today, UTC)."
    )
    merchant_id: uuid.UUID | None = Field(
        None, description="Limit the run to a single merchant."
    )
    dry_run: bool = Field(
        False, description="Compute what would be paid without creating payouts."
    )


class PayoutSkip(BaseModel):
    merchant_id: uuid.UUID
    reason: str


class PayoutRunResponse(BaseModel):
    payout_date: date
    dry_run: bool
    merchants_paid: int
    total_net_amount: float
    payouts: list[PayoutResponse]
    skipped: list[PayoutSkip]
