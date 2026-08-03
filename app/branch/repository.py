import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch


class BranchRepositoryInterface(ABC):
    """Abstract repository interface for Branch domain operations."""

    @abstractmethod
    async def create(self, branch: Branch) -> Branch:
        """Persist a new Branch entity."""

    @abstractmethod
    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None:
        """Fetch branch by ID if active and not soft deleted."""

    @abstractmethod
    async def list_by_brand_id(
        self, brand_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Branch]:
        """Fetch active branches under a specific brand."""

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Branch]:
        """Fetch active branches across all brands."""

    @abstractmethod
    async def update(self, branch: Branch) -> Branch:
        """Update existing branch entity."""

    @abstractmethod
    async def soft_delete(self, branch: Branch) -> None:
        """Soft delete branch entity."""


class BranchRepository(BranchRepositoryInterface):
    """Concrete SQLAlchemy implementation of BranchRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, branch: Branch) -> Branch:
        self.session.add(branch)
        await self.session.flush()
        await self.session.refresh(branch)
        return branch

    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None:
        stmt = select(Branch).where(
            Branch.id == branch_id,
            Branch.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_brand_id(
        self, brand_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Branch]:
        stmt = (
            select(Branch)
            .where(
                Branch.brand_id == brand_id,
                Branch.deleted_at.is_(None),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Branch]:
        stmt = (
            select(Branch).where(Branch.deleted_at.is_(None)).offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, branch: Branch) -> Branch:
        await self.session.flush()
        await self.session.refresh(branch)
        return branch

    async def soft_delete(self, branch: Branch) -> None:
        branch.deleted_at = datetime.now(UTC)
        await self.session.flush()
