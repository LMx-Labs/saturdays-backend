import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.repository import BranchRepositoryInterface
from app.brand.repository import BrandRepositoryInterface
from app.core.exceptions import (
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.kitchen.models import Kitchen
from app.kitchen.repository import KitchenRepositoryInterface
from app.kitchen.schemas import (
    KitchenCreateRequest,
    KitchenResponse,
    KitchenUpdateRequest,
)
from app.merchant.repository import MerchantRepositoryInterface


class KitchenServiceInterface(ABC):
    """Abstract service interface for kitchen domain operations."""

    @abstractmethod
    async def create_kitchen(
        self, user_id: str, role: str, req: KitchenCreateRequest
    ) -> KitchenResponse:
        """Create a new kitchen prep unit (INV-KITCH-001)."""

    @abstractmethod
    async def get_kitchen_by_id(
        self, kitchen_id: str, user_id: str, role: str
    ) -> KitchenResponse:
        """Retrieve kitchen profile by ID."""

    @abstractmethod
    async def list_branch_kitchens(
        self, branch_id: str, user_id: str, role: str, skip: int = 0, limit: int = 100
    ) -> list[KitchenResponse]:
        """List active kitchen units for a store branch."""

    @abstractmethod
    async def update_kitchen(
        self, kitchen_id: str, user_id: str, role: str, req: KitchenUpdateRequest
    ) -> KitchenResponse:
        """Update kitchen unit details."""

    @abstractmethod
    async def delete_kitchen(self, kitchen_id: str, user_id: str, role: str) -> None:
        """Soft delete a kitchen unit entity."""


class KitchenService(KitchenServiceInterface):
    """Concrete implementation of KitchenServiceInterface."""

    def __init__(
        self,
        session: AsyncSession,
        kitchen_repo: KitchenRepositoryInterface,
        branch_repo: BranchRepositoryInterface,
        brand_repo: BrandRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
    ) -> None:
        self.session = session
        self.kitchen_repo = kitchen_repo
        self.branch_repo = branch_repo
        self.brand_repo = brand_repo
        self.merchant_repo = merchant_repo

    async def create_kitchen(
        self, user_id: str, role: str, req: KitchenCreateRequest
    ) -> KitchenResponse:
        try:
            branch_uuid = uuid.UUID(req.branch_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid branch UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        # INV-KITCH-001 (Valid Branch Parent)
        branch = await self.branch_repo.get_by_id(branch_uuid)
        if not branch:
            raise EntityNotFoundError(
                message=f"Parent branch with ID '{req.branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )

        if role != "PlatformAdmin":
            brand = await self.brand_repo.get_by_id(branch.brand_id)
            merchant = (
                await self.merchant_repo.get_by_id(brand.merchant_id) if brand else None
            )
            if (
                not merchant or str(merchant.owner_user_id) != user_id
            ) and role not in {
                "BranchManager",
                "MerchantOwner",
            }:
                raise ForbiddenError(
                    message="You do not have permission to create a kitchen under this branch.",
                    error_code="KITCHEN_CREATE_FORBIDDEN",
                )

        kitchen = Kitchen(
            branch_id=branch.id,
            name=req.name,
            is_active=req.is_active,
        )

        saved = await self.kitchen_repo.create(kitchen)
        await self.session.commit()
        return self._to_response(saved)

    async def get_kitchen_by_id(
        self, kitchen_id: str, user_id: str, role: str
    ) -> KitchenResponse:
        try:
            kitchen_uuid = uuid.UUID(kitchen_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid kitchen UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        kitchen = await self.kitchen_repo.get_by_id(kitchen_uuid)
        if not kitchen:
            raise EntityNotFoundError(
                message=f"Kitchen unit with ID '{kitchen_id}' not found.",
                error_code="KITCHEN_NOT_FOUND",
            )
        return self._to_response(kitchen)

    async def list_branch_kitchens(
        self, branch_id: str, user_id: str, role: str, skip: int = 0, limit: int = 100
    ) -> list[KitchenResponse]:
        try:
            branch_uuid = uuid.UUID(branch_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid branch UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        branch = await self.branch_repo.get_by_id(branch_uuid)
        if not branch:
            raise EntityNotFoundError(
                message=f"Branch with ID '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )

        kitchens = await self.kitchen_repo.list_by_branch_id(
            branch_uuid, skip=skip, limit=limit
        )
        return [self._to_response(k) for k in kitchens]

    async def update_kitchen(
        self, kitchen_id: str, user_id: str, role: str, req: KitchenUpdateRequest
    ) -> KitchenResponse:
        kitchen_uuid = uuid.UUID(kitchen_id)
        kitchen = await self.kitchen_repo.get_by_id(kitchen_uuid)
        if not kitchen:
            raise EntityNotFoundError(
                message=f"Kitchen unit with ID '{kitchen_id}' not found.",
                error_code="KITCHEN_NOT_FOUND",
            )

        if role != "PlatformAdmin" and role not in {"BranchManager", "MerchantOwner"}:
            raise ForbiddenError(
                message="You do not have permission to update this kitchen unit.",
                error_code="KITCHEN_UPDATE_FORBIDDEN",
            )

        if req.name is not None:
            kitchen.name = req.name
        if req.is_active is not None:
            kitchen.is_active = req.is_active

        updated = await self.kitchen_repo.update(kitchen)
        await self.session.commit()
        return self._to_response(updated)

    async def delete_kitchen(self, kitchen_id: str, user_id: str, role: str) -> None:
        kitchen_uuid = uuid.UUID(kitchen_id)
        kitchen = await self.kitchen_repo.get_by_id(kitchen_uuid)
        if not kitchen:
            raise EntityNotFoundError(
                message=f"Kitchen unit with ID '{kitchen_id}' not found.",
                error_code="KITCHEN_NOT_FOUND",
            )

        if role != "PlatformAdmin" and role not in {"BranchManager", "MerchantOwner"}:
            raise ForbiddenError(
                message="You do not have permission to delete this kitchen unit.",
                error_code="KITCHEN_DELETE_FORBIDDEN",
            )

        await self.kitchen_repo.soft_delete(kitchen)
        await self.session.commit()

    def _to_response(self, kitchen: Kitchen) -> KitchenResponse:
        return KitchenResponse(
            id=str(kitchen.id),
            branch_id=str(kitchen.branch_id),
            name=kitchen.name,
            is_active=kitchen.is_active,
            created_at=kitchen.created_at,
            updated_at=kitchen.updated_at,
        )
