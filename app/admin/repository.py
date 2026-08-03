import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditLog, Banner
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order
from app.subscription.models import PlatformCommission


class AdminRepositoryInterface(ABC):
    @abstractmethod
    async def log_action(self, audit_log: AdminAuditLog) -> AdminAuditLog:
        pass

    @abstractmethod
    async def get_audit_logs(self, limit: int = 50) -> Sequence[AdminAuditLog]:
        pass

    @abstractmethod
    async def create_banner(self, banner: Banner) -> Banner:
        pass

    @abstractmethod
    async def get_banners(self, active_only: bool = True) -> Sequence[Banner]:
        pass

    @abstractmethod
    async def delete_banner(self, banner_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def get_analytics_overview(self) -> dict:
        pass


class AdminRepository(AdminRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(self, audit_log: AdminAuditLog) -> AdminAuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        await self.session.refresh(audit_log)
        return audit_log

    async def get_audit_logs(self, limit: int = 50) -> Sequence[AdminAuditLog]:
        stmt = (
            select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create_banner(self, banner: Banner) -> Banner:
        self.session.add(banner)
        await self.session.flush()
        await self.session.refresh(banner)
        return banner

    async def get_banners(self, active_only: bool = True) -> Sequence[Banner]:
        stmt = select(Banner)
        if active_only:
            stmt = stmt.where(Banner.is_active.is_(True))
        stmt = stmt.order_by(Banner.display_order.asc(), Banner.created_at.desc())
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def delete_banner(self, banner_id: uuid.UUID) -> None:
        stmt = delete(Banner).where(Banner.id == banner_id)
        await self.session.execute(stmt)

    async def get_analytics_overview(self) -> dict:
        # Total and active merchants
        res_m = await self.session.execute(select(func.count(Merchant.id)))
        total_merchants = res_m.scalar() or 0

        res_ma = await self.session.execute(
            select(func.count(Merchant.id)).where(Merchant.status == "APPROVED")
        )
        active_merchants = res_ma.scalar() or 0

        # Total orders & gross revenue
        res_o = await self.session.execute(
            select(
                func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0.0)
            )
        )
        row_o = res_o.one()
        total_orders = row_o[0] or 0
        gross_revenue = float(row_o[1] or 0.0)

        # Platform commissions total
        res_c = await self.session.execute(
            select(func.coalesce(func.sum(PlatformCommission.commission_amount), 0.0))
        )
        platform_commissions = float(res_c.scalar() or 0.0)

        # Total customers
        res_cust = await self.session.execute(
            select(func.count(CustomerProfile.id)).where(
                CustomerProfile.deleted_at.is_(None)
            )
        )
        total_customers = res_cust.scalar() or 0

        return {
            "total_merchants": total_merchants,
            "active_merchants": active_merchants,
            "total_orders": total_orders,
            "gross_revenue": gross_revenue,
            "platform_commissions": platform_commissions,
            "total_customers": total_customers,
        }
