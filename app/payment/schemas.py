import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaymentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    transaction_type: str
    razorpay_payment_id: str | None = None
    razorpay_order_id: str | None = None
    razorpay_signature: str | None = None
    amount: float
    status: str
    payload_snapshot: Any | None = None
    created_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    customer_profile_id: uuid.UUID
    amount: float
    currency: str
    created_at: datetime
    transactions: list[PaymentTransactionResponse] = []


class PaymentIntentCreateRequest(BaseModel):
    order_id: uuid.UUID
    amount: float = Field(..., gt=0)
    currency: str = "INR"


class PaymentIntentResponse(BaseModel):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    razorpay_order_id: str
    amount: float
    currency: str


class PaymentVerifyRequest(BaseModel):
    order_id: uuid.UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentVerifyResponse(BaseModel):
    success: bool
    payment_id: uuid.UUID
    order_id: uuid.UUID
    status: str


class RefundCreateRequest(BaseModel):
    amount: float = Field(..., gt=0)
    reason: str = Field(default="ORDER_CANCELLED", max_length=100)
