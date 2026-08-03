import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.merchant.models import Merchant
from app.merchant.repository import MerchantRepositoryInterface
from app.merchant.schemas import (
    MerchantOnboardRequest,
    MerchantResponse,
    MerchantStatusUpdateRequest,
    MerchantUpdateRequest,
)


class MerchantServiceInterface(ABC):
    """Abstract service interface for merchant domain operations."""

    @abstractmethod
    async def onboard_merchant(
        self, owner_user_id: str, req: MerchantOnboardRequest
    ) -> MerchantResponse:
        """Register and onboard a new merchant entity (INV-MERCH-001)."""

    @abstractmethod
    async def get_current_merchant_profile(
        self, owner_user_id: str
    ) -> MerchantResponse:
        """Retrieve merchant profile for current user."""

    @abstractmethod
    async def get_merchant_by_id(self, merchant_id: str) -> MerchantResponse:
        """Retrieve merchant profile by ID."""

    @abstractmethod
    async def update_merchant(
        self,
        merchant_id: str,
        owner_user_id: str,
        req: MerchantUpdateRequest,
        is_admin: bool = False,
    ) -> MerchantResponse:
        """Update merchant details."""

    @abstractmethod
    async def update_merchant_status(
        self, merchant_id: str, req: MerchantStatusUpdateRequest
    ) -> MerchantResponse:
        """Transition merchant lifecycle status (INV-MERCH-002)."""


from typing import ClassVar


class MerchantService(MerchantServiceInterface):
    """Concrete implementation of MerchantServiceInterface."""

    VALID_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "DRAFT": {"PENDING_VERIFICATION"},
        "PENDING_VERIFICATION": {"APPROVED", "REJECTED"},
        "REJECTED": {"DRAFT", "PENDING_VERIFICATION"},
        "APPROVED": {"SUSPENDED"},
        "SUSPENDED": {"APPROVED"},
    }

    def __init__(
        self,
        session: AsyncSession,
        merchant_repo: MerchantRepositoryInterface,
    ) -> None:
        self.session = session
        self.merchant_repo = merchant_repo

    async def onboard_merchant(
        self, owner_user_id: str, req: MerchantOnboardRequest
    ) -> MerchantResponse:
        owner_uuid = uuid.UUID(owner_user_id)

        # Check if user already owns a merchant account
        existing_merchant = await self.merchant_repo.get_by_owner_user_id(owner_uuid)
        if existing_merchant:
            raise ConflictError(
                message="User already owns a registered merchant account.",
                error_code="MERCHANT_ALREADY_EXISTS",
            )

        # INV-MERCH-001: Unique Tax ID (GSTIN)
        if req.gstin:
            existing_gstin = await self.merchant_repo.get_by_gstin(req.gstin)
            if existing_gstin:
                raise ConflictError(
                    message=f"A merchant with GSTIN '{req.gstin}' already exists.",
                    error_code="DUPLICATE_GSTIN",
                )

        merchant = Merchant(
            owner_user_id=owner_uuid,
            business_name=req.business_name,
            legal_entity_name=req.legal_entity_name,
            fssai_license_number=req.fssai_license_number,
            gstin=req.gstin,
            bank_account_number=req.bank_account_number,
            bank_ifsc_code=req.bank_ifsc_code,
            status="DRAFT",
        )

        saved = await self.merchant_repo.create(merchant)
        await self.session.commit()

        return MerchantResponse(
            id=str(saved.id),
            owner_user_id=str(saved.owner_user_id),
            business_name=saved.business_name,
            legal_entity_name=saved.legal_entity_name,
            gstin=saved.gstin,
            fssai_license_number=saved.fssai_license_number,
            bank_account_number=saved.bank_account_number,
            bank_ifsc_code=saved.bank_ifsc_code,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )

    async def get_current_merchant_profile(
        self, owner_user_id: str
    ) -> MerchantResponse:
        owner_uuid = uuid.UUID(owner_user_id)
        merchant = await self.merchant_repo.get_by_owner_user_id(owner_uuid)
        if not merchant:
            raise EntityNotFoundError(
                message="No merchant profile found for the current user.",
                error_code="MERCHANT_NOT_FOUND",
            )
        return self._to_response(merchant)

    async def get_merchant_by_id(self, merchant_id: str) -> MerchantResponse:
        try:
            merchant_uuid = uuid.UUID(merchant_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid merchant UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        merchant = await self.merchant_repo.get_by_id(merchant_uuid)
        if not merchant:
            raise EntityNotFoundError(
                message=f"Merchant with ID '{merchant_id}' not found.",
                error_code="MERCHANT_NOT_FOUND",
            )
        return self._to_response(merchant)

    async def update_merchant(
        self,
        merchant_id: str,
        owner_user_id: str,
        req: MerchantUpdateRequest,
        is_admin: bool = False,
    ) -> MerchantResponse:
        merchant_uuid = uuid.UUID(merchant_id)
        merchant = await self.merchant_repo.get_by_id(merchant_uuid)
        if not merchant:
            raise EntityNotFoundError(
                message=f"Merchant with ID '{merchant_id}' not found.",
                error_code="MERCHANT_NOT_FOUND",
            )

        if not is_admin and str(merchant.owner_user_id) != owner_user_id:
            raise ForbiddenError(
                message="You do not have permission to update this merchant account.",
                error_code="MERCHANT_UPDATE_FORBIDDEN",
            )

        if req.gstin and req.gstin != merchant.gstin:
            existing_gstin = await self.merchant_repo.get_by_gstin(req.gstin)
            if existing_gstin and existing_gstin.id != merchant.id:
                raise ConflictError(
                    message=f"A merchant with GSTIN '{req.gstin}' already exists.",
                    error_code="DUPLICATE_GSTIN",
                )
            merchant.gstin = req.gstin

        if req.business_name is not None:
            merchant.business_name = req.business_name
        if req.legal_entity_name is not None:
            merchant.legal_entity_name = req.legal_entity_name
        if req.fssai_license_number is not None:
            merchant.fssai_license_number = req.fssai_license_number
        if req.bank_account_number is not None:
            merchant.bank_account_number = req.bank_account_number
        if req.bank_ifsc_code is not None:
            merchant.bank_ifsc_code = req.bank_ifsc_code

        updated = await self.merchant_repo.update(merchant)
        await self.session.commit()
        return self._to_response(updated)

    async def update_merchant_status(
        self, merchant_id: str, req: MerchantStatusUpdateRequest
    ) -> MerchantResponse:
        merchant_uuid = uuid.UUID(merchant_id)
        merchant = await self.merchant_repo.get_by_id(merchant_uuid)
        if not merchant:
            raise EntityNotFoundError(
                message=f"Merchant with ID '{merchant_id}' not found.",
                error_code="MERCHANT_NOT_FOUND",
            )

        current_status = merchant.status
        target_status = req.status

        if target_status != current_status:
            allowed = self.VALID_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                raise DomainInvariantError(
                    message=f"Cannot transition merchant status from '{current_status}' to '{target_status}'. Allowed: {sorted(allowed)}",
                    error_code="INVALID_STATUS_TRANSITION",
                )
            merchant.status = target_status
            updated = await self.merchant_repo.update(merchant)
            await self.session.commit()
            return self._to_response(updated)

        return self._to_response(merchant)

    def _to_response(self, merchant: Merchant) -> MerchantResponse:
        return MerchantResponse(
            id=str(merchant.id),
            owner_user_id=str(merchant.owner_user_id),
            business_name=merchant.business_name,
            legal_entity_name=merchant.legal_entity_name,
            gstin=merchant.gstin,
            fssai_license_number=merchant.fssai_license_number,
            bank_account_number=merchant.bank_account_number,
            bank_ifsc_code=merchant.bank_ifsc_code,
            status=merchant.status,
            created_at=merchant.created_at,
            updated_at=merchant.updated_at,
        )
