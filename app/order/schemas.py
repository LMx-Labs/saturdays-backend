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
    store_credit_applied: float = 0.0
    status: str
    delivery_address_snapshot: Any
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = []
    status_logs: list[OrderStatusLogResponse] = []


class OrderCreateRequest(BaseModel):
    branch_id: uuid.UUID
    items: list[OrderItemCreate] = Field(..., min_length=1)
    delivery_address_snapshot: dict[str, Any]
    use_store_credit: bool = Field(
        False,
        description="Spend the customer's store credit for this brand against the order.",
    )


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="Target order status: PLACED, ACCEPTED, PREPARING, READY, COMPLETED, CANCELLED",
    )
    reason: str | None = None
