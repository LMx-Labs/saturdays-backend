from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _parse_time(v: Any) -> time:
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        parts = v.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return time(hour, minute, second)
    raise ValueError("Time must be in 'HH:MM:SS' or 'HH:MM' format")


class BranchCreateRequest(BaseModel):
    """Schema for creating a physical branch location."""

    brand_id: str = Field(..., description="UUID of parent brand entity")
    name: str = Field(
        ..., min_length=2, max_length=150, description="Branch display name"
    )
    address_text: str = Field(
        ..., min_length=2, max_length=255, description="Full physical address"
    )
    latitude: float | None = Field(
        None, ge=-90.0, le=90.0, description="Latitude coordinate"
    )
    longitude: float | None = Field(
        None, ge=-180.0, le=180.0, description="Longitude coordinate"
    )
    is_active: bool = Field(True, description="Initial active status toggle")
    opening_time: str = Field("08:00:00", description="Daily opening time (HH:MM:SS)")
    closing_time: str = Field("23:00:00", description="Daily closing time (HH:MM:SS)")

    @field_validator("opening_time", "closing_time", mode="before")
    @classmethod
    def validate_time(cls, v: Any) -> str:
        t = _parse_time(v)
        return t.strftime("%H:%M:%S")


class BranchUpdateRequest(BaseModel):
    """Schema for updating branch details."""

    name: str | None = Field(None, min_length=2, max_length=150)
    address_text: str | None = Field(None, min_length=2, max_length=255)
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    is_active: bool | None = None
    opening_time: str | None = None
    closing_time: str | None = None

    @field_validator("opening_time", "closing_time", mode="before")
    @classmethod
    def validate_time(cls, v: Any) -> str | None:
        if v is None:
            return None
        t = _parse_time(v)
        return t.strftime("%H:%M:%S")


class BranchStatusUpdateRequest(BaseModel):
    """Schema for toggling branch active status."""

    is_active: bool = Field(
        ..., description="Target active status (True=ONLINE, False=OFFLINE)"
    )


class BranchResponse(BaseModel):
    """Response model for branch entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    brand_id: str
    name: str
    address_text: str
    latitude: float | None
    longitude: float | None
    is_active: bool
    opening_time: str
    closing_time: str
    created_at: datetime
    updated_at: datetime

    @field_validator("opening_time", "closing_time", mode="before")
    @classmethod
    def format_time_str(cls, v: Any) -> str:
        if isinstance(v, time):
            return v.strftime("%H:%M:%S")
        return str(v)
