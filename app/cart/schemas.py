import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CartItemAddRequest(BaseModel):
    branch_id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int = Field(1, gt=0, description="Quantity must be greater than 0")
    selected_modifiers: list[dict[str, Any]] | None = None


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=0, description="Quantity (0 will remove item)")
    selected_modifiers: list[dict[str, Any]] | None = None


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cart_id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int
    selected_modifiers: Any | None = None
    menu_item_name: str | None = None
    unit_price: float | None = None
    subtotal: float | None = None
    is_available: bool | None = True
    created_at: datetime
    updated_at: datetime


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_profile_id: uuid.UUID
    branch_id: uuid.UUID
    items: list[CartItemResponse] = []
    total_items: int = 0
    subtotal: float = 0.0
    is_expired: bool = False
    created_at: datetime
    updated_at: datetime


class CartValidationIssue(BaseModel):
    code: str
    message: str
    item_id: uuid.UUID | None = None
    menu_item_id: uuid.UUID | None = None


class CartValidationResponse(BaseModel):
    is_valid: bool
    issues: list[CartValidationIssue] = []
    subtotal: float = 0.0
    total_items: int = 0
