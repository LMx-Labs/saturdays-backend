import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.garba.pricing import MAX_PER_BOOKING, attendee_count

_PHONE = re.compile(r"^[6-9]\d{9}$")
Category = Literal["men", "women", "couple"]
Dates = Literal["17", "18", "both"]


class AttendeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str

    @field_validator("name")
    @classmethod
    def _name_length(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Name must be at least 2 characters")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _indian_mobile(cls, value: str) -> str:
        if not _PHONE.fullmatch(value):
            raise ValueError("Phone must be a 10-digit Indian mobile number")
        return value


class GarbaBookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Category
    dates: Dates
    quantity: int = Field(ge=1)
    attendees: list[AttendeeIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _limits(self) -> "GarbaBookingCreateRequest":
        cap = MAX_PER_BOOKING[self.category]
        if self.quantity > cap:
            raise ValueError(f"Maximum {cap} {self.category} passes per booking")
        expected = attendee_count(self.category, self.quantity)
        if len(self.attendees) != expected:
            raise ValueError(f"Expected {expected} attendees for this pass")
        return self


class GarbaBookingCreateResponse(BaseModel):
    booking_id: uuid.UUID
    razorpay_order_id: str
    amount: int
    currency: str
    key_id: str
    is_simulated: bool


class GarbaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    razorpay_order_id: str = Field(min_length=1)
    razorpay_payment_id: str = Field(min_length=1)
    razorpay_signature: str = Field(min_length=1)


class GarbaPass(BaseModel):
    ticket_number: str
    name: str
    phone: str
    qr_token: str


class GarbaBookingResponse(BaseModel):
    id: uuid.UUID
    category: str
    dates: str
    quantity: int
    attendees: list[AttendeeIn]
    amount: int
    currency: str
    status: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    ticket_numbers: list[str]
    passes: list[GarbaPass] = []
    created_at: datetime


class GarbaAvailabilityResponse(BaseModel):
    name: str
    venue: str
    starts_at: str
    ends_at: str
    dates: dict[str, str]
    remaining: dict[str, dict[str, int]]
    capacity: dict[str, dict[str, int]]
    max_per_booking: dict[str, int]
    prices: dict[str, dict[str, int]]


class GarbaInventoryCell(BaseModel):
    category: str
    event_date: str
    capacity: int
    sold: int
    held: int
    remaining: int


class GarbaInventoryUpdate(BaseModel):
    category: Literal["men", "women", "couple"]
    event_date: Literal["17", "18"]
    capacity: int = Field(ge=0)


class GarbaScanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200)


class GarbaScanResponse(BaseModel):
    admitted: bool
    already_entered: bool
    ticket_number: str
    attendee_name: str
    attendee_phone: str
    category: str
    dates: str
    checked_in_at: datetime | None = None
