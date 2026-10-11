import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.branch.models import Branch
from app.brand.models import Brand
from app.subscription.models import MerchantSubscription, PlatformCommission


class SubscriptionRepositoryInterface(ABC):
    @abstractmethod
    async def get_active_subscription(
        self, merchant_id: uuid.UUID
    ) -> MerchantSubscription | None:
        pass

    @abstractmethod
    async def get_subscription_by_id(
        self, subscription_id: uuid.UUID
    ) -> MerchantSubscription | None:
        pass

    @abstractmethod
    async def list_subscriptions(
        self,
        merchant_id: uuid.UUID | None = None,
        status: str | None = None,
        plan_tier: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[MerchantSubscription]:
        pass

    @abstractmethod
    async def get_subscription_history(
        self,
        merchant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[MerchantSubscription]:
        pass

    @abstractmethod
    async def create_subscription(
        self, subscription: MerchantSubscription
    ) -> MerchantSubscription:
        pass

    @abstractmethod
    async def update_subscription(
        self, subscription: MerchantSubscription, update_data: dict
    ) -> MerchantSubscription:
        pass

    @abstractmethod
    async def record_commission(
        self, commission: PlatformCommission
    ) -> PlatformCommission:
        pass

    @abstractmethod
    async def get_merchant_commissions(
        self, merchant_id: uuid.UUID
    ) -> Sequence[PlatformCommission]:
        pass

    @abstractmethod
    async def count_merchant_branches(self, merchant_id: uuid.UUID) -> int:
        pass


class SubscriptionRepository(SubscriptionRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_subscription(
        self, merchant_id: uuid.UUID
    ) -> MerchantSubscription | None:
        stmt = (
            select(MerchantSubscription)
            .where(
                MerchantSubscription.merchant_id == merchant_id,
                MerchantSubscription.status == "ACTIVE",
                MerchantSubscription.deleted_at.is_(None),
            )
            .order_by(MerchantSubscription.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_subscription_by_id(
        self, subscription_id: uuid.UUID
    ) -> MerchantSubscription | None:
        stmt = (
            select(MerchantSubscription)
            .options(selectinload(MerchantSubscription.merchant))
            .where(
                MerchantSubscription.id == subscription_id,
                MerchantSubscription.deleted_at.is_(None),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_subscriptions(
        self,
        merchant_id: uuid.UUID | None = None,
        status: str | None = None,
        plan_tier: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[MerchantSubscription]:
        stmt = (
            select(MerchantSubscription)
            .options(selectinload(MerchantSubscription.merchant))
            .where(MerchantSubscription.deleted_at.is_(None))
        )
        if merchant_id:
            stmt = stmt.where(MerchantSubscription.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(
                func.upper(MerchantSubscription.status) == status.strip().upper()
            )
        if plan_tier:
            stmt = stmt.where(
                func.upper(MerchantSubscription.plan_tier) == plan_tier.strip().upper()
            )
        stmt = (
            stmt.order_by(
                MerchantSubscription.created_at.desc(),
                MerchantSubscription.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_subscription_history(
        self,
        merchant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[MerchantSubscription]:
        stmt = (
            select(MerchantSubscription)
            .options(selectinload(MerchantSubscription.merchant))
            .where(MerchantSubscription.deleted_at.is_(None))
        )
        if merchant_id:
            stmt = stmt.where(MerchantSubscription.merchant_id == merchant_id)
        stmt = (
            stmt.order_by(
                MerchantSubscription.created_at.desc(),
                MerchantSubscription.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create_subscription(
        self, subscription: MerchantSubscription
    ) -> MerchantSubscription:
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def update_subscription(
        self, subscription: MerchantSubscription, update_data: dict
    ) -> MerchantSubscription:
        for key, val in update_data.items():
            if hasattr(subscription, key) and val is not None:
                setattr(subscription, key, val)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def record_commission(
        self, commission: PlatformCommission
    ) -> PlatformCommission:
        self.session.add(commission)
        await self.session.flush()
        await self.session.refresh(commission)
        return commission

    async def get_merchant_commissions(
        self, merchant_id: uuid.UUID
    ) -> Sequence[PlatformCommission]:
        stmt = (
            select(PlatformCommission)
            .where(PlatformCommission.merchant_id == merchant_id)
            .order_by(PlatformCommission.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def count_merchant_branches(self, merchant_id: uuid.UUID) -> int:
        stmt = (
            select(func.count(Branch.id))
            .join(Brand, Branch.brand_id == Brand.id)
            .where(Brand.merchant_id == merchant_id, Branch.deleted_at.is_(None))
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0
