import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MenuModifierBase(BaseModel):
    name: str = Field(..., max_length=100)
    price_delta: float = Field(default=0.0, ge=0)


class MenuModifierCreate(MenuModifierBase):
    pass


class MenuModifierResponse(MenuModifierBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menu_item_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MenuItemBase(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    base_price: float = Field(..., description="Base price of item, must be >= 0.00")
    image_url: str | None = None
    is_available: bool = True
    is_veg: bool = True


class MenuItemCreate(MenuItemBase):
    category_id: uuid.UUID


class MenuItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_price: float | None = None
    image_url: str | None = None
    is_available: bool | None = None
    is_veg: bool | None = None
    category_id: uuid.UUID | None = None


class MenuItemResponse(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    modifiers: list[MenuModifierResponse] = []


class MenuCategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    display_order: int = 0


class MenuCategoryCreate(MenuCategoryBase):
    pass


class MenuCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    display_order: int | None = None


class MenuCategoryResponse(MenuCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menu_id: uuid.UUID
    items: list[MenuItemResponse] = []
    created_at: datetime
    updated_at: datetime


class MenuCreate(BaseModel):
    name: str = Field(default="Main Menu", max_length=100)
    is_active: bool = True


class MenuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    is_active: bool
    categories: list[MenuCategoryResponse] = []
    created_at: datetime
    updated_at: datetime
