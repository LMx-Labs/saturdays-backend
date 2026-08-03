from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BrandCreateRequest(BaseModel):
    """Schema for creating a new brand."""

    merchant_id: str | None = Field(
        None,
        description="UUID of owning merchant (optional if user has registered merchant)",
    )
    name: str = Field(
        ..., min_length=2, max_length=100, description="Public brand name"
    )
    logo_url: str | None = Field(None, max_length=255, description="Logo image URL")
    banner_url: str | None = Field(None, max_length=255, description="Banner image URL")
    description: str | None = Field(None, description="Brand story or description")
    cuisine_types: list[str] | None = Field(
        None, description="List of cuisine categories (e.g. ['Italian', 'Pizza'])"
    )


class BrandUpdateRequest(BaseModel):
    """Schema for updating brand details."""

    name: str | None = Field(None, min_length=2, max_length=100)
    logo_url: str | None = Field(None, max_length=255)
    banner_url: str | None = Field(None, max_length=255)
    description: str | None = None
    cuisine_types: list[str] | None = None


class BrandResponse(BaseModel):
    """Response model for brand entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    name: str
    logo_url: str | None
    banner_url: str | None
    description: str | None
    cuisine_types: list[str] | None
    created_at: datetime
    updated_at: datetime
