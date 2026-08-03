import uuid
from abc import ABC, abstractmethod
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch
from app.branch.repository import BranchRepositoryInterface
from app.branch.schemas import (
    BranchCreateRequest,
    BranchResponse,
    BranchStatusUpdateRequest,
    BranchUpdateRequest,
)
from app.brand.repository import BrandRepositoryInterface
from app.core.exceptions import (
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.merchant.repository import MerchantRepositoryInterface


def _parse_time_str(val: str) -> time:
    parts = val.split(":")
    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


class BranchServiceInterface(ABC):
    """Abstract service interface for branch domain operations."""

    @abstractmethod
    async def create_branch(
        self, user_id: str, is_admin: bool, req: BranchCreateRequest
    ) -> BranchResponse:
        """Create a new physical branch entity (INV-BRANCH-001)."""

    @abstractmethod
    async def get_branch_by_id(self, branch_id: str) -> BranchResponse:
        """Retrieve branch profile by ID."""

    @abstractmethod
    async def list_branches(
        self, brand_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[BranchResponse]:
        """List active branch locations."""

    @abstractmethod
    async def update_branch(
        self, branch_id: str, user_id: str, is_admin: bool, req: BranchUpdateRequest
    ) -> BranchResponse:
        """Update branch details."""

    @abstractmethod
    async def update_branch_status(
        self,
        branch_id: str,
        user_id: str,
        is_admin: bool,
        req: BranchStatusUpdateRequest,
    ) -> BranchResponse:
        """Toggle branch status (ONLINE/OFFLINE toggle)."""

    @abstractmethod
    async def delete_branch(self, branch_id: str, user_id: str, is_admin: bool) -> None:
        """Soft delete a branch entity."""


class BranchService(BranchServiceInterface):
    """Concrete implementation of BranchServiceInterface."""

    def __init__(
        self,
        session: AsyncSession,
        branch_repo: BranchRepositoryInterface,
        brand_repo: BrandRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
    ) -> None:
        self.session = session
        self.branch_repo = branch_repo
        self.brand_repo = brand_repo
        self.merchant_repo = merchant_repo

    async def create_branch(
        self, user_id: str, is_admin: bool, req: BranchCreateRequest
    ) -> BranchResponse:
        try:
            brand_uuid = uuid.UUID(req.brand_id)
        except ValueError as exc:
            raise DomainInvariantError(
                message="Invalid brand UUID format.",
                error_code="INVALID_UUID",
            ) from exc

        # INV-BRANCH-001 (Valid Brand Parent)
        brand = await self.brand_repo.get_by_id(brand_uuid)
        if not brand:
            raise EntityNotFoundError(
                message=f"Parent brand with ID '{req.brand_id}' not found.",
                error_code="BRAND_NOT_FOUND",
            )

        if not is_admin:
            merchant = await self.merchant_repo.get_by_id(brand.merchant_id)
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to create a branch under this brand.",
                    error_code="BRANCH_CREATE_FORBIDDEN",
                )

        opening_t = _parse_time_str(req.opening_time)
        closing_t = _parse_time_str(req.closing_time)

        branch = Branch(
            brand_id=brand.id,
            name=req.name,
            address_text=req.address_text,
            latitude=req.latitude,
            longitude=req.longitude,
            is_active=req.is_active,
            opening_time=opening_t,
            closing_time=closing_t,
        )

        saved = await self.branch_repo.create(branch)
        await self.session.commit()
        return self._to_response(saved)

    async def get_branch_by_id(self, branch_id: str) -> BranchResponse:
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
        return self._to_response(branch)

    async def list_branches(
        self, brand_id: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[BranchResponse]:
        if brand_id:
            try:
                brand_uuid = uuid.UUID(brand_id)
            except ValueError as exc:
                raise DomainInvariantError(
                    message="Invalid brand UUID format.",
                    error_code="INVALID_UUID",
                ) from exc
            branches = await self.branch_repo.list_by_brand_id(
                brand_uuid, skip=skip, limit=limit
            )
        else:
            branches = await self.branch_repo.list_all(skip=skip, limit=limit)

        return [self._to_response(b) for b in branches]

    async def update_branch(
        self, branch_id: str, user_id: str, is_admin: bool, req: BranchUpdateRequest
    ) -> BranchResponse:
        branch_uuid = uuid.UUID(branch_id)
        branch = await self.branch_repo.get_by_id(branch_uuid)
        if not branch:
            raise EntityNotFoundError(
                message=f"Branch with ID '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )

        if not is_admin:
            brand = await self.brand_repo.get_by_id(branch.brand_id)
            merchant = (
                await self.merchant_repo.get_by_id(brand.merchant_id) if brand else None
            )
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to update this branch.",
                    error_code="BRANCH_UPDATE_FORBIDDEN",
                )

        if req.name is not None:
            branch.name = req.name
        if req.address_text is not None:
            branch.address_text = req.address_text
        if req.latitude is not None:
            branch.latitude = req.latitude
        if req.longitude is not None:
            branch.longitude = req.longitude
        if req.is_active is not None:
            branch.is_active = req.is_active
        if req.opening_time is not None:
            branch.opening_time = _parse_time_str(req.opening_time)
        if req.closing_time is not None:
            branch.closing_time = _parse_time_str(req.closing_time)

        updated = await self.branch_repo.update(branch)
        await self.session.commit()
        return self._to_response(updated)

    async def update_branch_status(
        self,
        branch_id: str,
        user_id: str,
        is_admin: bool,
        req: BranchStatusUpdateRequest,
    ) -> BranchResponse:
        branch_uuid = uuid.UUID(branch_id)
        branch = await self.branch_repo.get_by_id(branch_uuid)
        if not branch:
            raise EntityNotFoundError(
                message=f"Branch with ID '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )

        if not is_admin:
            brand = await self.brand_repo.get_by_id(branch.brand_id)
            merchant = (
                await self.merchant_repo.get_by_id(brand.merchant_id) if brand else None
            )
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to update status for this branch.",
                    error_code="BRANCH_UPDATE_FORBIDDEN",
                )

        branch.is_active = req.is_active
        updated = await self.branch_repo.update(branch)
        await self.session.commit()
        return self._to_response(updated)

    async def delete_branch(self, branch_id: str, user_id: str, is_admin: bool) -> None:
        branch_uuid = uuid.UUID(branch_id)
        branch = await self.branch_repo.get_by_id(branch_uuid)
        if not branch:
            raise EntityNotFoundError(
                message=f"Branch with ID '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )

        if not is_admin:
            brand = await self.brand_repo.get_by_id(branch.brand_id)
            merchant = (
                await self.merchant_repo.get_by_id(brand.merchant_id) if brand else None
            )
            if not merchant or str(merchant.owner_user_id) != user_id:
                raise ForbiddenError(
                    message="You do not have permission to delete this branch.",
                    error_code="BRANCH_DELETE_FORBIDDEN",
                )

        await self.branch_repo.soft_delete(branch)
        await self.session.commit()

    def _to_response(self, branch: Branch) -> BranchResponse:
        return BranchResponse(
            id=str(branch.id),
            brand_id=str(branch.brand_id),
            name=branch.name,
            address_text=branch.address_text,
            latitude=float(branch.latitude) if branch.latitude is not None else None,
            longitude=float(branch.longitude) if branch.longitude is not None else None,
            is_active=branch.is_active,
            opening_time=branch.opening_time.strftime("%H:%M:%S"),
            closing_time=branch.closing_time.strftime("%H:%M:%S"),
            created_at=branch.created_at,
            updated_at=branch.updated_at,
        )
