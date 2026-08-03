import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.merchant.models import Merchant


class MerchantRepositoryInterface(ABC):
    """Abstract interface for Merchant repository operations."""

    @abstractmethod
    async def create(self, merchant: Merchant) -> Merchant:
        """Persist a new merchant entity."""

    @abstractmethod
    async def get_by_id(self, merchant_id: uuid.UUID) -> Merchant | None:
        """Fetch merchant by ID if not soft deleted."""

    @abstractmethod
    async def get_by_owner_user_id(self, owner_user_id: uuid.UUID) -> Merchant | None:
        """Fetch active merchant owned by user ID."""

    @abstractmethod
    async def get_by_gstin(self, gstin: str) -> Merchant | None:
        """Fetch merchant by unique GSTIN if not soft deleted."""

    @abstractmethod
    async def get_by_fssai(self, fssai_license_number: str) -> Merchant | None:
        """Fetch merchant by FSSAI license number if not soft deleted."""

    @abstractmethod
    async def update(self, merchant: Merchant) -> Merchant:
        """Update existing merchant entity."""


class MerchantRepository(MerchantRepositoryInterface):
    """Concrete SQLAlchemy implementation of MerchantRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, merchant: Merchant) -> Merchant:
        self.session.add(merchant)
        await self.session.flush()
        await self.session.refresh(merchant)
        return merchant

    async def get_by_id(self, merchant_id: uuid.UUID) -> Merchant | None:
        stmt = select(Merchant).where(
            Merchant.id == merchant_id,
            Merchant.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner_user_id(self, owner_user_id: uuid.UUID) -> Merchant | None:
        stmt = select(Merchant).where(
            Merchant.owner_user_id == owner_user_id,
            Merchant.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_gstin(self, gstin: str) -> Merchant | None:
        stmt = select(Merchant).where(
            Merchant.gstin == gstin,
            Merchant.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_fssai(self, fssai_license_number: str) -> Merchant | None:
        stmt = select(Merchant).where(
            Merchant.fssai_license_number == fssai_license_number,
            Merchant.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, merchant: Merchant) -> Merchant:
        await self.session.flush()
        await self.session.refresh(merchant)
        return merchant
