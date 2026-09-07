import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    selected_modifiers_snapshot: list[dict[str, Any]] | None = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    menu_item_id: uuid.UUID
    item_name_snapshot: str
    unit_price_snapshot: float
    quantity: int
    selected_modifiers_snapshot: Any | None = None
    created_at: datetime


class OrderStatusLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    previous_status: str | None = None
    new_status: str
    changed_by_user_id: uuid.UUID
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_profile_id: uuid.UUID
    branch_id: uuid.UUID
    total_amount: float
    subtotal: float
    discount_amount: float
    tax_amount: float
    delivery_fee: float
    currency: str
    checkout_quote_id: uuid.UUID | None = None
    cancellation_reason: str | None = None
    status: str
    delivery_address_snapshot: Any
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = []
    status_logs: list[OrderStatusLogResponse] = []


class OrderCreateRequest(BaseModel):
    quote_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    items: list[OrderItemCreate] = []
    delivery_address_snapshot: dict[str, Any] = {}


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="Target order status: PLACED, ACCEPTED, PREPARING, READY, COMPLETED, CANCELLED",
    )
    reason: str | None = None
