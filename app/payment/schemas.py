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
    provider: str
    provider_order_id: str | None = None
    created_at: datetime
    transactions: list[PaymentTransactionResponse] = []


class PaymentPage(BaseModel):
    items: list[PaymentResponse]
    page: int
    page_size: int
    total: int
    pages: int


class PaymentIntentCreateRequest(BaseModel):
    order_id: uuid.UUID
    amount: float | None = Field(None, gt=0, description="Ignored; derived from order")
    currency: str | None = Field(None, description="Ignored; derived from order")


class PaymentIntentResponse(BaseModel):
    payment_id: uuid.UUID
    order_id: uuid.UUID
    razorpay_order_id: str
    amount: float
    currency: str
    provider: str = "mock"
    provider_key_id: str | None = None


class MockPaymentCompleteRequest(BaseModel):
    order_id: uuid.UUID


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
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)
