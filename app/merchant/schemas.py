import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MerchantOnboardRequest(BaseModel):
    """Schema for merchant onboarding request."""

    business_name: str = Field(
        ..., min_length=2, max_length=150, description="Trading/business name"
    )
    legal_entity_name: str = Field(
        ..., min_length=2, max_length=150, description="Registered legal entity name"
    )
    fssai_license_number: str = Field(..., description="14-digit FSSAI license number")
    gstin: str | None = Field(None, description="15-character GSTIN tax identifier")
    bank_account_number: str | None = Field(
        None, max_length=50, description="Bank account number"
    )
    bank_ifsc_code: str | None = Field(
        None, max_length=20, description="Bank IFSC code"
    )

    @field_validator("fssai_license_number")
    @classmethod
    def validate_fssai(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{14}$", v):
            raise ValueError("FSSAI license number must be exactly 14 digits")
        return v

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if v and not re.match(
            r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", v
        ):
            raise ValueError("Invalid GSTIN format")
        return v


class MerchantUpdateRequest(BaseModel):
    """Schema for updating merchant details."""

    business_name: str | None = Field(None, min_length=2, max_length=150)
    legal_entity_name: str | None = Field(None, min_length=2, max_length=150)
    fssai_license_number: str | None = None
    gstin: str | None = None
    bank_account_number: str | None = None
    bank_ifsc_code: str | None = None

    @field_validator("fssai_license_number")
    @classmethod
    def validate_fssai(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not re.match(r"^\d{14}$", v):
            raise ValueError("FSSAI license number must be exactly 14 digits")
        return v

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if v and not re.match(
            r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", v
        ):
            raise ValueError("Invalid GSTIN format")
        return v


class MerchantStatusUpdateRequest(BaseModel):
    """Schema for updating merchant lifecycle status."""

    status: str = Field(
        ...,
        description="Target status (DRAFT, PENDING_VERIFICATION, APPROVED, REJECTED, SUSPENDED)",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {
            "DRAFT",
            "PENDING_VERIFICATION",
            "APPROVED",
            "REJECTED",
            "SUSPENDED",
        }
        v_upper = v.upper()
        if v_upper not in valid_statuses:
            raise ValueError(
                f"Status must be one of: {', '.join(sorted(valid_statuses))}"
            )
        return v_upper


class MerchantResponse(BaseModel):
    """Response model for merchant entity."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_user_id: str
    business_name: str
    legal_entity_name: str
    gstin: str | None
    fssai_license_number: str
    bank_account_number: str | None
    bank_ifsc_code: str | None
    status: str
    created_at: datetime
    updated_at: datetime
