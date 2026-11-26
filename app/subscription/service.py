import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError, UnprocessableEntityError
from app.merchant.repository import MerchantRepositoryInterface
from app.subscription.models import MerchantSubscription, PlatformCommission
from app.subscription.repository import SubscriptionRepositoryInterface
from app.subscription.schemas import (
    MerchantSubscriptionResponse,
    PlatformCommissionResponse,
    SubscriptionCreateRequest,
    SubscriptionInvoiceResponse,
    SubscriptionRenewalRequest,
)

PLAN_DETAILS = {
    "BASIC": {"max_branches": 1, "commission_rate": 7.00, "price": 999.0, "max_orders_per_day": 40},
    "PROFESSIONAL": {"max_branches": 5, "commission_rate": 5.00, "price": 2499.0, "max_orders_per_day": 100},
    "ENTERPRISE": {"max_branches": 20, "commission_rate": 3.50, "price": 4999.0, "max_orders_per_day": 200},
}


class SubscriptionServiceInterface(ABC):
    @abstractmethod
    async def get_active_subscription(
        self, user_id: uuid.UUID
    ) -> MerchantSubscriptionResponse:
        pass

    @abstractmethod
    async def create_subscription(
        self, user_id: uuid.UUID, req: SubscriptionCreateRequest
    ) -> MerchantSubscriptionResponse:
        pass

    @abstractmethod
    async def renew_subscription(
        self, user_id: uuid.UUID, req: SubscriptionRenewalRequest
    ) -> MerchantSubscriptionResponse:
        pass

    @abstractmethod
    async def calculate_and_record_commission(
        self, order_id: uuid.UUID, merchant_id: uuid.UUID, gross_order_amount: float
    ) -> PlatformCommissionResponse:
        pass

    @abstractmethod
    async def get_merchant_commissions(
        self, user_id: uuid.UUID
    ) -> list[PlatformCommissionResponse]:
        pass

    @abstractmethod
    async def get_merchant_invoices(
        self, user_id: uuid.UUID
    ) -> list[SubscriptionInvoiceResponse]:
        pass

    @abstractmethod
    async def validate_branch_limit(self, merchant_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def check_daily_order_quota(self, merchant_id: uuid.UUID) -> None:
        pass


class SubscriptionService(SubscriptionServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        sub_repo: SubscriptionRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
    ):
        self.session = session
        self.sub_repo = sub_repo
        self.merchant_repo = merchant_repo

    async def _get_merchant_by_user_id(self, user_id: uuid.UUID):
        merchant = await self.merchant_repo.get_by_owner_user_id(user_id)
        if not merchant:
            raise EntityNotFoundError(
                message="Merchant profile not found.", error_code="MERCHANT_NOT_FOUND"
            )
        return merchant

    def _to_sub_response(
        self, sub: MerchantSubscription
    ) -> MerchantSubscriptionResponse:
        tier_info = PLAN_DETAILS.get(sub.plan_tier, PLAN_DETAILS["BASIC"])
        return MerchantSubscriptionResponse(
            id=sub.id,
            merchant_id=sub.merchant_id,
            plan_tier=sub.plan_tier,
            billing_cycle=sub.billing_cycle,
            status=sub.status,
            commission_rate_percentage=float(sub.commission_rate_percentage),
            max_branches=int(tier_info["max_branches"]),
            valid_until=sub.valid_until,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )

    async def get_active_subscription(
        self, user_id: uuid.UUID
    ) -> MerchantSubscriptionResponse:
        merchant = await self._get_merchant_by_user_id(user_id)
        sub = await self.sub_repo.get_active_subscription(merchant.id)
        if not sub:
            # Auto-initialize default BASIC subscription
            now = datetime.now(UTC)
            sub = MerchantSubscription(
                merchant_id=merchant.id,
                plan_tier="BASIC",
                billing_cycle="MONTHLY",
                status="ACTIVE",
                commission_rate_percentage=5.00,
                valid_until=now + timedelta(days=3650),  # 10 year default
            )
            sub = await self.sub_repo.create_subscription(sub)
            await self.session.commit()

        return self._to_sub_response(sub)

    async def create_subscription(
        self, user_id: uuid.UUID, req: SubscriptionCreateRequest
    ) -> MerchantSubscriptionResponse:
        merchant = await self._get_merchant_by_user_id(user_id)
        tier = req.plan_tier.upper()

        if tier not in PLAN_DETAILS:
            raise UnprocessableEntityError(
                message=f"Invalid plan tier '{req.plan_tier}'. Must be BASIC, PROFESSIONAL, or ENTERPRISE.",
                error_code="INVALID_PLAN_TIER",
            )

        tier_info = PLAN_DETAILS[tier]
        now = datetime.now(UTC)
        valid_until = (
            now + timedelta(days=365)
            if req.billing_cycle.upper() == "ANNUAL"
            else now + timedelta(days=30)
        )

        existing_sub = await self.sub_repo.get_active_subscription(merchant.id)
        if existing_sub:
            await self.sub_repo.update_subscription(
                existing_sub, {"status": "SUPERSEDED"}
            )

        sub = MerchantSubscription(
            merchant_id=merchant.id,
            plan_tier=tier,
            billing_cycle=req.billing_cycle.upper(),
            status="ACTIVE",
            commission_rate_percentage=tier_info["commission_rate"],
            valid_until=valid_until,
        )

        created = await self.sub_repo.create_subscription(sub)
        await self.session.commit()
        return self._to_sub_response(created)

    async def renew_subscription(
        self, user_id: uuid.UUID, req: SubscriptionRenewalRequest
    ) -> MerchantSubscriptionResponse:
        merchant = await self._get_merchant_by_user_id(user_id)
        sub = await self.sub_repo.get_active_subscription(merchant.id)

        now = datetime.now(UTC)
        if not sub:
            valid_until = now + timedelta(days=30 * req.duration_months)
            new_tier = req.plan_tier.upper() if req.plan_tier else "BASIC"
            tier_info = PLAN_DETAILS.get(new_tier, PLAN_DETAILS["BASIC"])
            sub = MerchantSubscription(
                merchant_id=merchant.id,
                plan_tier=new_tier,
                billing_cycle="MONTHLY",
                status="ACTIVE",
                commission_rate_percentage=tier_info["commission_rate"],
                valid_until=valid_until,
            )
            created = await self.sub_repo.create_subscription(sub)
            await self.session.commit()
            return self._to_sub_response(created)

        # Extend existing subscription
        current_expiry = (
            sub.valid_until
            if sub.valid_until.tzinfo
            else sub.valid_until.replace(tzinfo=UTC)
        )
        base_time = max(now, current_expiry)
        new_expiry = base_time + timedelta(days=30 * req.duration_months)

        update_data = {"valid_until": new_expiry, "status": "ACTIVE"}

        if req.plan_tier:
            tier = req.plan_tier.upper()
            if tier in PLAN_DETAILS:
                update_data["plan_tier"] = tier
                update_data["commission_rate_percentage"] = PLAN_DETAILS[tier][
                    "commission_rate"
                ]

        updated = await self.sub_repo.update_subscription(sub, update_data)
        await self.session.commit()
        return self._to_sub_response(updated)

    async def calculate_and_record_commission(
        self, order_id: uuid.UUID, merchant_id: uuid.UUID, gross_order_amount: float
    ) -> PlatformCommissionResponse:
        # Check active subscription for commission rate
        sub = await self.sub_repo.get_active_subscription(merchant_id)
        rate = float(sub.commission_rate_percentage) if sub else 5.00

        # INV-SUB-001: Immutable Commission Ledger Calculation
        commission_amount = round(gross_order_amount * (rate / 100.0), 2)
        merchant_net_payout = round(gross_order_amount - commission_amount, 2)

        comm = PlatformCommission(
            order_id=order_id,
            merchant_id=merchant_id,
            gross_order_amount=gross_order_amount,
            commission_rate_percentage=rate,
            commission_amount=commission_amount,
            merchant_net_payout=merchant_net_payout,
        )

        recorded = await self.sub_repo.record_commission(comm)
        await self.session.commit()

        return PlatformCommissionResponse.model_validate(recorded)

    async def get_merchant_commissions(
        self, user_id: uuid.UUID
    ) -> list[PlatformCommissionResponse]:
        merchant = await self._get_merchant_by_user_id(user_id)
        commissions = await self.sub_repo.get_merchant_commissions(merchant.id)
        return [PlatformCommissionResponse.model_validate(c) for c in commissions]

    async def get_merchant_invoices(
        self, user_id: uuid.UUID
    ) -> list[SubscriptionInvoiceResponse]:
        merchant = await self._get_merchant_by_user_id(user_id)
        sub = await self.sub_repo.get_active_subscription(merchant.id)
        if not sub:
            return []

        tier_info = PLAN_DETAILS.get(sub.plan_tier, PLAN_DETAILS["BASIC"])
        inv_num = f"INV-SUB-{sub.id.hex[:8].upper()}"

        return [
            SubscriptionInvoiceResponse(
                invoice_number=inv_num,
                merchant_id=merchant.id,
                subscription_id=sub.id,
                plan_tier=sub.plan_tier,
                amount=tier_info["price"],
                billing_cycle=sub.billing_cycle,
                valid_until=sub.valid_until,
                issued_at=sub.created_at,
            )
        ]

    async def validate_branch_limit(self, merchant_id: uuid.UUID) -> None:
        sub = await self.sub_repo.get_active_subscription(merchant_id)
        plan_tier = sub.plan_tier if sub else "BASIC"
        max_allowed = PLAN_DETAILS.get(plan_tier, PLAN_DETAILS["BASIC"])["max_branches"]

        if max_allowed == -1:
            return  # Unlimited

        current_branches = await self.sub_repo.count_merchant_branches(merchant_id)
        if current_branches >= max_allowed:
            raise UnprocessableEntityError(
                message=f"Branch creation limit reached for your '{plan_tier}' subscription tier (Max: {max_allowed}).",
                error_code="SUBSCRIPTION_BRANCH_LIMIT_EXCEEDED",
            )

    async def check_daily_order_quota(self, merchant_id: uuid.UUID) -> None:
        sub = await self.sub_repo.get_active_subscription(merchant_id)
        plan_tier = sub.plan_tier if sub else "BASIC"
        tier_info = PLAN_DETAILS.get(plan_tier, PLAN_DETAILS["BASIC"])
        max_orders = (
            sub.max_orders_per_day
            if sub and sub.max_orders_per_day is not None
            else tier_info.get("max_orders_per_day", 40)
        )
        if max_orders == -1:
            return

        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from sqlalchemy import func, select
        from app.order.models import Order
        from app.branch.models import Branch
        from app.brand.models import Brand

        stmt = (
            select(func.count(Order.id))
            .select_from(Order)
            .join(Branch, Branch.id == Order.branch_id)
            .join(Brand, Brand.id == Branch.brand_id)
            .where(
                Brand.merchant_id == merchant_id,
                Order.created_at >= today_start,
                Order.status != "CANCELLED",
            )
        )
        res = await self.session.execute(stmt)
        count = res.scalar() or 0

        if count >= max_orders:
            raise UnprocessableEntityError(
                message=f"Daily order limit reached for your '{plan_tier}' plan ({max_orders} orders/day). Please upgrade your plan to accept more orders.",
                error_code="ORDER_QUOTA_EXCEEDED",
            )
