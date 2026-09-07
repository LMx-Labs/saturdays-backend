import uuid
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction
from app.subscription.models import PlatformCommission


class ReportsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _dates(stmt, column, date_from: datetime | None, date_to: datetime | None):
        if date_from:
            stmt = stmt.where(column >= date_from)
        if date_to:
            stmt = stmt.where(column <= date_to)
        return stmt

    async def sales(
        self, branch_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ):
        stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.discount_amount), 0),
            func.coalesce(func.avg(Order.total_amount), 0),
            func.coalesce(
                func.sum(case((Order.status.in_(["COMPLETED", "DELIVERED"]), 1), else_=0)), 0
            ),
            func.coalesce(func.sum(case((Order.status == "CANCELLED", 1), else_=0)), 0),
        ).where(Order.branch_id == branch_id)
        stmt = self._dates(stmt, Order.created_at, date_from, date_to)
        return (await self.session.execute(stmt)).one()

    async def payments(
        self, branch_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ):
        payments = (
            select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .join(Order, Order.id == Payment.order_id)
            .where(Order.branch_id == branch_id)
        )
        payments = self._dates(payments, Payment.created_at, date_from, date_to)
        payment_row = (await self.session.execute(payments)).one()
        refunds = (
            select(
                func.count(PaymentTransaction.id),
                func.coalesce(func.sum(PaymentTransaction.amount), 0),
            )
            .join(Payment, Payment.id == PaymentTransaction.payment_id)
            .join(Order, Order.id == Payment.order_id)
            .where(
                Order.branch_id == branch_id,
                PaymentTransaction.transaction_type == "REFUND",
                PaymentTransaction.status.in_(["PROCESSED", "SUCCESS", "CAPTURED"]),
            )
        )
        refunds = self._dates(refunds, PaymentTransaction.created_at, date_from, date_to)
        return payment_row, (await self.session.execute(refunds)).one()

    async def commissions(
        self, merchant_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ):
        stmt = select(
            func.count(PlatformCommission.id),
            func.coalesce(func.sum(PlatformCommission.gross_order_amount), 0),
            func.coalesce(func.sum(PlatformCommission.commission_amount), 0),
            func.coalesce(func.sum(PlatformCommission.merchant_net_payout), 0),
        ).where(PlatformCommission.merchant_id == merchant_id)
        stmt = self._dates(stmt, PlatformCommission.created_at, date_from, date_to)
        return (await self.session.execute(stmt)).one()

    async def platform(self, date_from: datetime | None, date_to: datetime | None):
        merchant_count = await self.session.scalar(select(func.count(Merchant.id))) or 0
        approved = (
            await self.session.scalar(
                select(func.count(Merchant.id)).where(Merchant.status == "APPROVED")
            )
            or 0
        )
        branches = (
            await self.session.scalar(
                select(func.count(Branch.id)).where(Branch.deleted_at.is_(None))
            )
            or 0
        )
        customers = (
            await self.session.scalar(
                select(func.count(CustomerProfile.id)).where(CustomerProfile.deleted_at.is_(None))
            )
            or 0
        )
        orders = select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        orders = self._dates(orders, Order.created_at, date_from, date_to)
        order_count, gross = (await self.session.execute(orders)).one()
        return merchant_count, approved, branches, customers, order_count, gross
