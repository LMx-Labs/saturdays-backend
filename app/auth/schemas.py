from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User's unique email address")
    password: str = Field(
        ..., min_length=8, description="Plaintext password (minimum 8 characters)"
    )
    role: str = Field(
        default="Customer",
        description="User role (Customer, KitchenStaff, BranchManager, MerchantOwner, PlatformAdmin)",
    )


class UserLoginRequest(BaseModel):
    """Schema for user authentication request."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="Plaintext password")


class TokenRefreshRequest(BaseModel):
    """Schema for refreshing access tokens."""

    refresh_token: str = Field(..., description="Valid 7-day JWT refresh token")


class UserResponse(BaseModel):
    """Schema for user entity response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    branch_id: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Schema for token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds
    user: UserResponse


class UserClaims(BaseModel):
    """Schema representing authenticated user claims extracted from JWT."""

    sub: str
    email: str
    role: str
    branch_id: str | None = None
