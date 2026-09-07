import uuid
from datetime import UTC, datetime

from app.reports.repository import ReportsRepository
from app.reports.schemas import (
    BranchPerformance,
    CommissionSummary,
    PaymentRefundSummary,
    PlatformOperationalSummary,
    SalesSummary,
)


class ReportsService:
    def __init__(self, repository: ReportsRepository):
        self.repository = repository

    async def sales(
        self, branch_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ):
        count, gross, discounts, average, completed, cancelled = await self.repository.sales(
            branch_id, date_from, date_to
        )
        return (
            SalesSummary(
                order_count=count,
                gross_sales=float(gross),
                discounts=float(discounts),
                net_sales=float(gross) - float(discounts),
                average_order_value=float(average),
            ),
            completed,
            cancelled,
        )

    async def branch_performance(
        self, branch_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ) -> BranchPerformance:
        summary, completed, cancelled = await self.sales(branch_id, date_from, date_to)
        return BranchPerformance(
            branch_id=branch_id,
            **summary.model_dump(),
            completed_orders=completed,
            cancelled_orders=cancelled,
        )

    async def payments(
        self, branch_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ) -> PaymentRefundSummary:
        payments, refunds = await self.repository.payments(branch_id, date_from, date_to)
        return PaymentRefundSummary(
            payment_count=payments[0],
            payment_amount=float(payments[1]),
            refund_count=refunds[0],
            refund_amount=float(refunds[1]),
        )

    async def commissions(
        self, merchant_id: uuid.UUID, date_from: datetime | None, date_to: datetime | None
    ) -> CommissionSummary:
        row = await self.repository.commissions(merchant_id, date_from, date_to)
        return CommissionSummary(
            commission_count=row[0],
            gross_order_amount=float(row[1]),
            commission_amount=float(row[2]),
            merchant_net_payout=float(row[3]),
        )

    async def platform(
        self, date_from: datetime | None, date_to: datetime | None
    ) -> PlatformOperationalSummary:
        row = await self.repository.platform(date_from, date_to)
        return PlatformOperationalSummary(
            merchant_count=row[0],
            approved_merchant_count=row[1],
            branch_count=row[2],
            customer_count=row[3],
            order_count=row[4],
            gross_sales=float(row[5]),
            generated_at=datetime.now(UTC),
        )
