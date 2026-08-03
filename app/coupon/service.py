import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    EntityNotFoundError,
    UnprocessableEntityError,
)
from app.coupon.models import Coupon
from app.coupon.repository import CouponRepositoryInterface
from app.coupon.schemas import (
    CouponCreate,
    CouponResponse,
    CouponValidateRequest,
    CouponValidateResponse,
)
from app.customer.repository import CustomerRepositoryInterface


class CouponServiceInterface(ABC):
    @abstractmethod
    async def create_coupon(self, req: CouponCreate) -> CouponResponse:
        pass

    @abstractmethod
    async def validate_coupon(
        self, user_id: uuid.UUID, req: CouponValidateRequest
    ) -> CouponValidateResponse:
        pass

    @abstractmethod
    async def list_available_coupons(
        self, branch_id: uuid.UUID | None = None
    ) -> list[CouponResponse]:
        pass

    @abstractmethod
    async def get_coupon_by_id(self, coupon_id: uuid.UUID) -> CouponResponse:
        pass


class CouponService(CouponServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        coupon_repo: CouponRepositoryInterface,
        customer_repo: CustomerRepositoryInterface,
    ):
        self.session = session
        self.coupon_repo = coupon_repo
        self.customer_repo = customer_repo

    def _to_response(self, coupon: Coupon) -> CouponResponse:
        return CouponResponse(
            id=coupon.id,
            branch_id=coupon.branch_id,
            code=coupon.code,
            discount_type=coupon.discount_type,
            discount_value=float(coupon.discount_value),
            max_discount_amount=(
                float(coupon.max_discount_amount)
                if coupon.max_discount_amount is not None
                else None
            ),
            min_order_amount=float(coupon.min_order_amount),
            max_redemptions_per_user=coupon.max_redemptions_per_user,
            valid_from=coupon.valid_from,
            valid_until=coupon.valid_until,
            is_active=coupon.is_active,
            is_platform_coupon=coupon.branch_id is None,
            created_at=coupon.created_at,
            updated_at=coupon.updated_at,
        )

    async def create_coupon(self, req: CouponCreate) -> CouponResponse:
        existing = await self.coupon_repo.get_by_code(req.code)
        if existing:
            raise ConflictError(
                message=f"Coupon code '{req.code.upper()}' already exists.",
                error_code="COUPON_CODE_EXISTS",
            )

        if req.discount_type not in ("PERCENTAGE", "FLAT"):
            raise UnprocessableEntityError(
                message="Discount type must be either 'PERCENTAGE' or 'FLAT'.",
                error_code="INVALID_DISCOUNT_TYPE",
            )

        if req.discount_type == "PERCENTAGE" and req.discount_value > 100:
            raise UnprocessableEntityError(
                message="Percentage discount value cannot exceed 100%.",
                error_code="INVALID_DISCOUNT_VALUE",
            )

        coupon = Coupon(
            code=req.code.strip().upper(),
            branch_id=req.branch_id,
            discount_type=req.discount_type,
            discount_value=req.discount_value,
            max_discount_amount=req.max_discount_amount,
            min_order_amount=req.min_order_amount,
            max_redemptions_per_user=req.max_redemptions_per_user,
            valid_from=req.valid_from,
            valid_until=req.valid_until,
            is_active=req.is_active,
        )

        created = await self.coupon_repo.create_coupon(coupon)
        await self.session.commit()
        return self._to_response(created)

    async def validate_coupon(
        self, user_id: uuid.UUID, req: CouponValidateRequest
    ) -> CouponValidateResponse:
        coupon = await self.coupon_repo.get_by_code(req.code)

        # 1. Existence and Active status
        if not coupon or not coupon.is_active or coupon.deleted_at is not None:
            raise EntityNotFoundError(
                message="Invalid or inactive coupon code.",
                error_code="COUPON_NOT_FOUND",
            )

        # Ensure timezone-aware datetime comparison
        now = datetime.now(UTC)
        valid_from = (
            coupon.valid_from
            if coupon.valid_from.tzinfo
            else coupon.valid_from.replace(tzinfo=UTC)
        )
        valid_until = (
            coupon.valid_until
            if coupon.valid_until.tzinfo
            else coupon.valid_until.replace(tzinfo=UTC)
        )

        # 2. Time Window Check
        if now < valid_from or now > valid_until:
            raise UnprocessableEntityError(
                message="Coupon promotional period is not currently active.",
                error_code="COUPON_EXPIRED",
            )

        # 3. Scope Check (Platform Coupon vs Restaurant Coupon)
        # Platform Coupon: branch_id is None -> valid everywhere
        # Restaurant Coupon: branch_id is NOT None -> valid ONLY for specified branch_id
        if coupon.branch_id is not None and (
            not req.branch_id or req.branch_id != coupon.branch_id
        ):
            raise UnprocessableEntityError(
                message="Coupon is not valid for this restaurant/branch.",
                error_code="COUPON_BRANCH_MISMATCH",
            )

        # 4. Minimum Order Amount Check
        min_order = float(coupon.min_order_amount)
        if req.order_amount < min_order:
            raise UnprocessableEntityError(
                message=f"Minimum order amount of ₹{min_order:.2f} is required for this coupon.",
                error_code="MINIMUM_ORDER_AMOUNT_NOT_MET",
            )

        # 5. User Redemption Limit Check (INV-CPN-001)
        profile = await self.customer_repo.get_by_user_id(user_id)
        if profile:
            redemptions_count = await self.coupon_repo.count_user_redemptions(
                coupon.id, profile.id
            )
            if redemptions_count >= coupon.max_redemptions_per_user:
                raise UnprocessableEntityError(
                    message=f"You have reached the maximum redemption limit ({coupon.max_redemptions_per_user}) for this coupon.",
                    error_code="COUPON_USAGE_LIMIT_REACHED",
                )

        # 6. Discount Calculation Engine
        order_amount = req.order_amount
        disc_val = float(coupon.discount_value)

        if coupon.discount_type == "PERCENTAGE":
            raw_discount = order_amount * (disc_val / 100.0)
            if coupon.max_discount_amount is not None:
                max_disc = float(coupon.max_discount_amount)
                discount_amount = min(raw_discount, max_disc)
            else:
                discount_amount = raw_discount
        else:  # FLAT
            discount_amount = min(disc_val, order_amount)

        discount_amount = round(discount_amount, 2)
        final_amount = max(0.0, round(order_amount - discount_amount, 2))

        return CouponValidateResponse(
            is_valid=True,
            coupon_id=coupon.id,
            code=coupon.code,
            discount_type=coupon.discount_type,
            discount_amount=discount_amount,
            final_amount=final_amount,
            message="Coupon applied successfully.",
        )

    async def list_available_coupons(
        self, branch_id: uuid.UUID | None = None
    ) -> list[CouponResponse]:
        coupons = await self.coupon_repo.list_active_coupons(branch_id=branch_id)
        return [self._to_response(c) for c in coupons]

    async def get_coupon_by_id(self, coupon_id: uuid.UUID) -> CouponResponse:
        coupon = await self.coupon_repo.get_by_id(coupon_id)
        if not coupon:
            raise EntityNotFoundError(
                message="Coupon not found.", error_code="COUPON_NOT_FOUND"
            )
        return self._to_response(coupon)
