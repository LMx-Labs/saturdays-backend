import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class StaffInviteRequest(BaseModel):
    email: EmailStr
    role: str
    branch_ids: list[uuid.UUID] = Field(default_factory=list)


class StaffUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    branch_ids: list[uuid.UUID] | None = None


class StaffResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    branch_ids: list[uuid.UUID]
    created_at: datetime


class StaffInvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    branch_ids: list[str]
    expires_at: datetime
    preview_token: str | None = None
