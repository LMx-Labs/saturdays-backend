from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KitchenCreateRequest(BaseModel):
    """Schema for creating a kitchen prep unit."""

    branch_id: str = Field(..., description="UUID of parent store branch entity")
    name: str = Field(
        "Main Kitchen", min_length=2, max_length=150, description="Kitchen station name"
    )
    is_active: bool = Field(True, description="Initial active status")


class KitchenUpdateRequest(BaseModel):
    """Schema for updating kitchen unit details."""

    name: str | None = Field(None, min_length=2, max_length=150)
    is_active: bool | None = None


class KitchenResponse(BaseModel):
    """Response model for kitchen entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    branch_id: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
