import uuid
from datetime import datetime

from pydantic import BaseModel


class SalesSummary(BaseModel):
    order_count: int
    gross_sales: float
    discounts: float
    net_sales: float
    average_order_value: float


class BranchPerformance(SalesSummary):
    branch_id: uuid.UUID
    completed_orders: int
    cancelled_orders: int


class PaymentRefundSummary(BaseModel):
    payment_count: int
    payment_amount: float
    refund_count: int
    refund_amount: float


class CommissionSummary(BaseModel):
    commission_count: int
    gross_order_amount: float
    commission_amount: float
    merchant_net_payout: float


class PlatformOperationalSummary(BaseModel):
    merchant_count: int
    approved_merchant_count: int
    branch_count: int
    customer_count: int
    order_count: int
    gross_sales: float
    generated_at: datetime
