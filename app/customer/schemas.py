import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone_number: str | None = None
    created_at: datetime
    updated_at: datetime


class CustomerProfileCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str | None = Field(None, max_length=20)


class CustomerProfileUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=100)
    phone_number: str | None = Field(None, max_length=20)


class CustomerAddressCreate(BaseModel):
    address_line: str = Field(..., min_length=1, max_length=255)
    building_name: str | None = Field(None, max_length=100)
    campus_zone: str = Field(..., min_length=1, max_length=100)
    is_primary: bool = False


class CustomerAddressUpdate(BaseModel):
    address_line: str | None = Field(None, min_length=1, max_length=255)
    building_name: str | None = Field(None, max_length=100)
    campus_zone: str | None = Field(None, min_length=1, max_length=100)
    is_primary: bool | None = None


class CustomerAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_profile_id: uuid.UUID
    address_line: str
    building_name: str | None = None
    campus_zone: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class CustomerFavoriteCreate(BaseModel):
    branch_id: uuid.UUID


class CustomerFavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_profile_id: uuid.UUID
    branch_id: uuid.UUID
    created_at: datetime
