import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str
    is_verified: bool = True


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str
    merchant_id: uuid.UUID | None = None
    branch_ids: list[uuid.UUID] = Field(default_factory=list)


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    merchant_id: uuid.UUID | None
    branch_ids: list[str]
    expires_at: datetime
    preview_token: str | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
