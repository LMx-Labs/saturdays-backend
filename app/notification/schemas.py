import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationSendRequest(BaseModel):
    recipient: str = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    channel: str = Field("EMAIL", description="Delivery channel (EMAIL, SMS, PUSH)")


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    recipient: str
    subject: str | None = None
    body: str
    status: str
    vendor_message_id: str | None = None
    created_at: datetime
