import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    change_amount: int
    previous_quantity: int
    new_quantity: int
    reason: str
    created_at: datetime


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int
    is_in_stock: bool
    created_at: datetime
    updated_at: datetime


class StockUpdateRequest(BaseModel):
    quantity: int = Field(..., description="Target stock quantity, must be >= 0")
    is_in_stock: bool | None = None
    reason: str = Field(default="MERCHANT_RESTOCK", max_length=100)


class StockReservationRequest(BaseModel):
    branch_id: uuid.UUID
    menu_item_id: uuid.UUID
    quantity: int = Field(..., gt=0, description="Quantity to reserve")


class InventoryItemCreateRequest(BaseModel):
    menu_item_id: uuid.UUID
    initial_quantity: int = Field(default=0, ge=0)
