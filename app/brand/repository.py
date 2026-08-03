import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brand.models import Brand


class BrandRepositoryInterface(ABC):
    """Abstract repository interface for Brand domain operations."""

    @abstractmethod
    async def create(self, brand: Brand) -> Brand:
        """Persist a new Brand entity."""

    @abstractmethod
    async def get_by_id(self, brand_id: uuid.UUID) -> Brand | None:
        """Fetch brand by ID if active and not soft deleted."""

    @abstractmethod
    async def list_by_merchant_id(
        self, merchant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Brand]:
        """Fetch active brands under a specific merchant."""

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Brand]:
        """Fetch active brands across all merchants."""

    @abstractmethod
    async def update(self, brand: Brand) -> Brand:
        """Update existing brand entity."""

    @abstractmethod
    async def soft_delete(self, brand: Brand) -> None:
        """Soft delete brand entity."""


class BrandRepository(BrandRepositoryInterface):
    """Concrete SQLAlchemy implementation of BrandRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, brand: Brand) -> Brand:
        self.session.add(brand)
        await self.session.flush()
        await self.session.refresh(brand)
        return brand

    async def get_by_id(self, brand_id: uuid.UUID) -> Brand | None:
        stmt = select(Brand).where(
            Brand.id == brand_id,
            Brand.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_merchant_id(
        self, merchant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Brand]:
        stmt = (
            select(Brand)
            .where(
                Brand.merchant_id == merchant_id,
                Brand.deleted_at.is_(None),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Brand]:
        stmt = select(Brand).where(Brand.deleted_at.is_(None)).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, brand: Brand) -> Brand:
        await self.session.flush()
        await self.session.refresh(brand)
        return brand

    async def soft_delete(self, brand: Brand) -> None:
        brand.deleted_at = datetime.now(UTC)
        await self.session.flush()
