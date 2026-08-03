import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kitchen.models import Kitchen


class KitchenRepositoryInterface(ABC):
    """Abstract repository interface for Kitchen domain operations."""

    @abstractmethod
    async def create(self, kitchen: Kitchen) -> Kitchen:
        """Persist a new Kitchen entity."""

    @abstractmethod
    async def get_by_id(self, kitchen_id: uuid.UUID) -> Kitchen | None:
        """Fetch kitchen unit by ID if active and not soft deleted."""

    @abstractmethod
    async def list_by_branch_id(
        self, branch_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Kitchen]:
        """Fetch active kitchen units under a specific branch."""

    @abstractmethod
    async def update(self, kitchen: Kitchen) -> Kitchen:
        """Update existing kitchen unit entity."""

    @abstractmethod
    async def soft_delete(self, kitchen: Kitchen) -> None:
        """Soft delete kitchen unit entity."""


class KitchenRepository(KitchenRepositoryInterface):
    """Concrete SQLAlchemy implementation of KitchenRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, kitchen: Kitchen) -> Kitchen:
        self.session.add(kitchen)
        await self.session.flush()
        await self.session.refresh(kitchen)
        return kitchen

    async def get_by_id(self, kitchen_id: uuid.UUID) -> Kitchen | None:
        stmt = select(Kitchen).where(
            Kitchen.id == kitchen_id,
            Kitchen.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_branch_id(
        self, branch_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Kitchen]:
        stmt = (
            select(Kitchen)
            .where(
                Kitchen.branch_id == branch_id,
                Kitchen.deleted_at.is_(None),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, kitchen: Kitchen) -> Kitchen:
        await self.session.flush()
        await self.session.refresh(kitchen)
        return kitchen

    async def soft_delete(self, kitchen: Kitchen) -> None:
        kitchen.deleted_at = datetime.now(UTC)
        await self.session.flush()
