import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coupon.models import Coupon, CouponRedemption


class CouponRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_code(self, code: str) -> Coupon | None:
        pass

    @abstractmethod
    async def get_by_id(self, coupon_id: uuid.UUID) -> Coupon | None:
        pass

    @abstractmethod
    async def create_coupon(self, coupon: Coupon) -> Coupon:
        pass

    @abstractmethod
    async def count_user_redemptions(
        self, coupon_id: uuid.UUID, customer_profile_id: uuid.UUID
    ) -> int:
        pass

    @abstractmethod
    async def record_redemption(self, redemption: CouponRedemption) -> CouponRedemption:
        pass

    @abstractmethod
    async def list_active_coupons(
        self, branch_id: uuid.UUID | None = None
    ) -> Sequence[Coupon]:
        pass


class CouponRepository(CouponRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Coupon | None:
        stmt = select(Coupon).where(
            func.lower(Coupon.code) == code.strip().lower(),
            Coupon.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, coupon_id: uuid.UUID) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.id == coupon_id, Coupon.deleted_at.is_(None))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_coupon(self, coupon: Coupon) -> Coupon:
        self.session.add(coupon)
        await self.session.flush()
        await self.session.refresh(coupon)
        return coupon

    async def count_user_redemptions(
        self, coupon_id: uuid.UUID, customer_profile_id: uuid.UUID
    ) -> int:
        stmt = select(func.count(CouponRedemption.id)).where(
            CouponRedemption.coupon_id == coupon_id,
            CouponRedemption.customer_profile_id == customer_profile_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def record_redemption(self, redemption: CouponRedemption) -> CouponRedemption:
        self.session.add(redemption)
        await self.session.flush()
        await self.session.refresh(redemption)
        return redemption

    async def list_active_coupons(
        self, branch_id: uuid.UUID | None = None
    ) -> Sequence[Coupon]:
        now = datetime.now(UTC)
        stmt = select(Coupon).where(
            Coupon.is_active.is_(True),
            Coupon.deleted_at.is_(None),
            Coupon.valid_from <= now,
            Coupon.valid_until >= now,
        )
        if branch_id:
            # Include platform coupons (branch_id is null) or branch-specific coupons
            stmt = stmt.where(
                (Coupon.branch_id.is_(None)) | (Coupon.branch_id == branch_id)
            )

        res = await self.session.execute(stmt)
        return res.scalars().all()
