import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.brand.models import Brand
from app.brand.repository import BrandRepositoryInterface
from app.brand.schemas import BrandCreateRequest, BrandResponse, BrandUpdateRequest
from app.core.exceptions import (
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.merchant.repository import MerchantRepositoryInterface


class BrandServiceInterface(ABC):
    """Abstract service interface for brand domain operations."""

    @abstractmethod
    async def create_brand(
        self, user_id: str, is_admin: bool, req: BrandCreateRequest
    ) -> BrandResponse:
        """Create a new brand entity (INV-BRAND-001)."""

    @abstractmethod
    async def get_brand_by_id(self, brand_id: str) -> BrandResponse:
        """Retrieve brand details by ID."""

    @abstractmethod
    async def list_brands(
        self, merchant_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[BrandResponse]:
        """List active brands."""

    @abstractmethod
    async def update_brand(
        self, brand_id: str, user_id: str, is_admin: bool, req: BrandUpdateRequest
    ) -> BrandResponse:
        """Update brand details."""

    @abstractmethod
    async def delete_brand(self, brand_id: str, user_id: str, is_admin: bool) -> None:
        """Soft delete a brand entity."""


class BrandService(BrandServiceInterface):
    """Concrete implementation of BrandServiceInterface."""

    def __init__(
        self,
        session: AsyncSession,
        brand_repo: BrandRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
    ) -> None:
        self.session = session
        self.brand_repo = brand_repo
        self.merchant_repo = merchant_repo

    async def create_brand(
        self, user_id: str, is_admin: bool, req: BrandCreateRequest
    ) -> BrandResponse:
        user_uuid = uuid.UUID(user_id)

        # Determine target merchant
        if req.merchant_id:
            try:
                merchant_uuid = uuid.UUID(req.merchant_id)
            except ValueError as exc:
                raise DomainInvariantError(
                    message="Invalid merchant UUID format.",
                    error_code="INVALID_UUID",
                ) from exc
            merchant = await self.merchant_repo.get_by_id(merchant_uuid)
        else:
            merchant = await self.merchant_repo.get_by_owner_user_id(user_uuid)

        # INV-BRAND-001 (Valid Merchant Parent)
        if not merchant:
            raise EntityNotFoundError(
                message="Valid merchant entity required to create brand.",
                error_code="MERCHANT_NOT_FOUND",
            )

        if not is_admin and str(merchant.owner_user_id) != user_id:
            raise ForbiddenError(
                message="You do not have permission to create a brand under this merchant.",
                error_code="BRAND_CREATE_FORBIDDEN",
            )

        brand = Brand(
            merchant_id=merchant.id,
            name=req.name,
            logo_url=req.logo_url,
            banner_url=req.banner_url,
            description=req.description,
            cuisine_types=req.cuisine_types,
        )

        saved = await self.brand_repo.create(brand)
        await self.session.commit()
        return self._to_response(saved)

    async def get_brand_by_id(self, brand_id: str) -> BrandResponse:
        try:
            brand_uuid = uuid.UUID(brand_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid brand UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        brand = await self.brand_repo.get_by_id(brand_uuid)
        if not brand:
            raise EntityNotFoundError(
                message=f"Brand with ID '{brand_id}' not found.",
                error_code="BRAND_NOT_FOUND",
            )
        return self._to_response(brand)

    async def list_brands(
        self, merchant_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[BrandResponse]:
        if merchant_id:
            try:
                merchant_uuid = uuid.UUID(merchant_id)
            except ValueError as exc:
                raise DomainInvariantError(
                    message="Invalid merchant UUID format.",
                    error_code="INVALID_UUID",
                ) from exc
            brands = await self.brand_repo.list_by_merchant_id(
                merchant_uuid, skip=skip, limit=limit
            )
        else:
            brands = await self.brand_repo.list_all(skip=skip, limit=limit)

        return [self._to_response(b) for b in brands]

    async def update_brand(
        self, brand_id: str, user_id: str, is_admin: bool, req: BrandUpdateRequest
    ) -> BrandResponse:
        brand_uuid = uuid.UUID(brand_id)
        brand = await self.brand_repo.get_by_id(brand_uuid)
        if not brand:
            raise EntityNotFoundError(
                message=f"Brand with ID '{brand_id}' not found.",
                error_code="BRAND_NOT_FOUND",
            )

        if not is_admin:
            merchant = await self.merchant_repo.get_by_id(brand.merchant_id)
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to update this brand.",
                    error_code="BRAND_UPDATE_FORBIDDEN",
                )

        if req.name is not None:
            brand.name = req.name
        if req.logo_url is not None:
            brand.logo_url = req.logo_url
        if req.banner_url is not None:
            brand.banner_url = req.banner_url
        if req.description is not None:
            brand.description = req.description
        if req.cuisine_types is not None:
            brand.cuisine_types = req.cuisine_types

        updated = await self.brand_repo.update(brand)
        await self.session.commit()
        return self._to_response(updated)

    async def delete_brand(self, brand_id: str, user_id: str, is_admin: bool) -> None:
        brand_uuid = uuid.UUID(brand_id)
        brand = await self.brand_repo.get_by_id(brand_uuid)
        if not brand:
            raise EntityNotFoundError(
                message=f"Brand with ID '{brand_id}' not found.",
                error_code="BRAND_NOT_FOUND",
            )

        if not is_admin:
            merchant = await self.merchant_repo.get_by_id(brand.merchant_id)
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to delete this brand.",
                    error_code="BRAND_DELETE_FORBIDDEN",
                )

        await self.brand_repo.soft_delete(brand)
        await self.session.commit()

    def _to_response(self, brand: Brand) -> BrandResponse:
        return BrandResponse(
            id=str(brand.id),
            merchant_id=str(brand.merchant_id),
            name=brand.name,
            logo_url=brand.logo_url,
            banner_url=brand.banner_url,
            description=brand.description,
            cuisine_types=brand.cuisine_types,
            created_at=brand.created_at,
            updated_at=brand.updated_at,
        )
