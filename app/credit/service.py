import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch
from app.core.config import settings
from app.core.exceptions import EntityNotFoundError
from app.credit.models import StoreCredit, StoreCreditTransaction
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction

logger = structlog.get_logger()

_CENT = Decimal("0.01")


def _money(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(_CENT, rounding=ROUND_HALF_UP)


class StoreCreditService:
    """Issues and redeems brand-scoped store credit.

    Methods never commit: callers own the transaction so that credit changes are
    atomic with the order change that triggered them.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ----- queries -----------------------------------------------------

    async def _brand_id_for_branch(self, branch_id: uuid.UUID) -> uuid.UUID:
        brand_id = (
            await self.session.execute(
                select(Branch.brand_id).where(Branch.id == branch_id)
            )
        ).scalar_one_or_none()
        if brand_id is None:
            raise EntityNotFoundError(
                message=f"Branch '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )
        return brand_id

    async def brand_id_for_branch(self, branch_id: uuid.UUID) -> uuid.UUID:
        return await self._brand_id_for_branch(branch_id)

    def _spendable(self, customer_profile_id: uuid.UUID, brand_id: uuid.UUID):
        return (
            select(StoreCredit)
            .where(
                StoreCredit.customer_profile_id == customer_profile_id,
                StoreCredit.brand_id == brand_id,
                StoreCredit.balance > 0,
                StoreCredit.expires_at > datetime.now(UTC),
            )
            .order_by(StoreCredit.expires_at.asc(), StoreCredit.created_at.asc())
        )

    async def get_balance(
        self, customer_profile_id: uuid.UUID, brand_id: uuid.UUID
    ) -> float:
        stmt = select(func.coalesce(func.sum(StoreCredit.balance), 0)).where(
            StoreCredit.customer_profile_id == customer_profile_id,
            StoreCredit.brand_id == brand_id,
            StoreCredit.expires_at > datetime.now(UTC),
        )
        return float(_money((await self.session.execute(stmt)).scalar_one()))

    async def list_credits(self, customer_profile_id: uuid.UUID) -> list[StoreCredit]:
        stmt = (
            select(StoreCredit)
            .where(StoreCredit.customer_profile_id == customer_profile_id)
            .order_by(StoreCredit.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ----- issuing -----------------------------------------------------

    async def issue(
        self,
        customer_profile_id: uuid.UUID,
        brand_id: uuid.UUID,
        amount: float,
        reason: str,
        source_order_id: uuid.UUID | None = None,
    ) -> StoreCredit:
        amount_d = _money(amount)
        credit = StoreCredit(
            customer_profile_id=customer_profile_id,
            brand_id=brand_id,
            source_order_id=source_order_id,
            initial_amount=amount_d,
            balance=amount_d,
            reason=reason,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.STORE_CREDIT_VALIDITY_DAYS),
        )
        self.session.add(credit)
        await self.session.flush()
        self.session.add(
            StoreCreditTransaction(
                credit_id=credit.id,
                transaction_type="ISSUED",
                amount=amount_d,
                order_id=source_order_id,
            )
        )
        await self.session.flush()
        logger.info(
            "StoreCreditIssuedEvent",
            credit_id=str(credit.id),
            customer_profile_id=str(customer_profile_id),
            brand_id=str(brand_id),
            amount=float(amount_d),
            reason=reason,
        )
        return credit

    async def issue_for_cancelled_order(self, order: Order) -> StoreCredit | None:
        """Convert what the customer paid for a cancelled order into store credit.

        Value returned = captured online payments (net of any refunds) plus any
        credit the customer had applied to the order. Idempotent per order.
        """
        existing = (
            await self.session.execute(
                select(StoreCredit).where(StoreCredit.source_order_id == order.id)
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        paid = await self.net_captured_amount(order.id)
        value = paid + _money(order.store_credit_applied)
        if value <= 0:
            return None

        brand_id = await self._brand_id_for_branch(order.branch_id)
        return await self.issue(
            customer_profile_id=order.customer_profile_id,
            brand_id=brand_id,
            amount=float(value),
            reason="ORDER_CANCELLED",
            source_order_id=order.id,
        )

    async def net_captured_amount(self, order_id: uuid.UUID) -> Decimal:
        """Money actually captured for an order, minus successful refunds."""

        async def _sum(tx_type: str) -> Decimal:
            stmt = (
                select(func.coalesce(func.sum(PaymentTransaction.amount), 0))
                .join(Payment, Payment.id == PaymentTransaction.payment_id)
                .where(
                    Payment.order_id == order_id,
                    PaymentTransaction.transaction_type == tx_type,
                    PaymentTransaction.status == "SUCCESS",
                )
            )
            return _money((await self.session.execute(stmt)).scalar_one())

        # A verified payment writes both VERIFIED and CAPTURED rows for the same
        # money; only CAPTURED counts.
        captured = await _sum("CAPTURED")
        refunded = await _sum("REFUNDED")
        return max(Decimal("0.00"), captured - refunded)

    # ----- redeeming ---------------------------------------------------

    async def redeem(
        self,
        customer_profile_id: uuid.UUID,
        brand_id: uuid.UUID,
        max_amount: float,
        order_id: uuid.UUID,
    ) -> float:
        """Spend up to ``max_amount`` (soonest-expiring credit first).

        Rows are locked (``FOR UPDATE``) so concurrent checkouts cannot overspend.
        Returns the amount actually applied.
        """
        remaining = _money(max_amount)
        if remaining <= 0:
            return 0.0

        rows = (
            (
                await self.session.execute(
                    self._spendable(customer_profile_id, brand_id).with_for_update()
                )
            )
            .scalars()
            .all()
        )
        applied = Decimal("0.00")
        for credit in rows:
            if remaining <= 0:
                break
            take = min(_money(credit.balance), remaining)
            credit.balance = _money(credit.balance) - take
            remaining -= take
            applied += take
            self.session.add(
                StoreCreditTransaction(
                    credit_id=credit.id,
                    transaction_type="REDEEMED",
                    amount=take,
                    order_id=order_id,
                )
            )
        await self.session.flush()
        if applied > 0:
            logger.info(
                "StoreCreditRedeemedEvent",
                order_id=str(order_id),
                brand_id=str(brand_id),
                amount=float(applied),
            )
        return float(applied)
