import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    order_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5, description="Rating between 1 and 5 stars")
    comment: str | None = Field(None, max_length=1000)


class ReviewReply(BaseModel):
    merchant_reply: str = Field(..., min_length=1, max_length=1000)


class ReviewModerateRequest(BaseModel):
    is_hidden: bool


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    customer_profile_id: uuid.UUID
    branch_id: uuid.UUID
    rating: int
    comment: str | None = None
    merchant_reply: str | None = None
    is_hidden: bool = False
    created_at: datetime
    updated_at: datetime


class RestaurantRatingSummary(BaseModel):
    branch_id: uuid.UUID
    average_rating: float
    total_reviews: int
    rating_distribution: dict[int, int]
