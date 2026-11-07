import json
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
    UnprocessableEntityError,
)
from app.credit.service import StoreCreditService
from app.customer.models import CustomerProfile
from app.notification.whatsapp_service import ORDER_CONFIRMED, WhatsAppNotifier
from app.order.models import Order
from app.order.placement import (
    CANCELLED_EARLIER,
    PENDING_PAYMENT,
    order_is_paid,
    place_paid_order,
)
from app.payment.models import Payment, PaymentTransaction
from app.payment.razorpay_adapter import RazorpayAdapter
from app.payment.repository import PaymentRepositoryInterface
from app.payment.schemas import (
    PaymentIntentResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    RefundCreateRequest,
)

logger = structlog.get_logger()


def ensure_refunds_enabled() -> None:
    """Cash refunds are disabled by policy; cancelled orders earn store credit."""
    if not settings.REFUNDS_ENABLED:
        raise DomainInvariantError(
            message=(
                "Cash refunds are not offered. Cancelled or unfulfilled orders are "
                "converted into store credit automatically."
            ),
            error_code="REFUNDS_DISABLED_USE_STORE_CREDIT",
        )


class PaymentServiceInterface(ABC):
    @abstractmethod
    async def create_payment_intent(
        self,
        customer_profile_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: float,
        currency: str = "INR",
    ) -> PaymentIntentResponse:
        pass

    @abstractmethod
    async def verify_payment(self, req: PaymentVerifyRequest) -> PaymentVerifyResponse:
        pass

    @abstractmethod
    async def process_webhook(
        self, raw_body: str | bytes, signature: str
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def refund_payment(
        self, payment_id: uuid.UUID, req: RefundCreateRequest
    ) -> PaymentTransaction:
        pass

    @abstractmethod
    async def get_payment_history(self, payment_id: uuid.UUID) -> Payment:
        pass


class PaymentService(PaymentServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        payment_repo: PaymentRepositoryInterface,
        razorpay_adapter: RazorpayAdapter | None = None,
        whatsapp: WhatsAppNotifier | None = None,
    ):
        self.session = session
        self.payment_repo = payment_repo
        self.razorpay_adapter = razorpay_adapter or RazorpayAdapter()
        self.whatsapp = whatsapp

    async def _tell_customer_order_is_confirmed(self, order_id: uuid.UUID) -> None:
        """WhatsApp "order confirmed": sent once the money is in, from either the student's own
        confirmation or Razorpay's webhook, whichever arrives first (the second finds it already
        sent). Never fails the payment."""
        if self.whatsapp is not None:
            await self.whatsapp.notify(order_id, ORDER_CONFIRMED)

    async def _check_order_can_be_paid(
        self, customer_profile_id: uuid.UUID, order_id: uuid.UUID, amount: float
    ) -> None:
        """Only the order's own customer can pay for it, only while it is waiting for payment, and
        only the amount it really costs. (Without this, anyone could ask for a payment of Rs 1 against
        a Rs 150 order and have it treated as paid.)"""
        order = await self.session.get(Order, order_id)
        if order is None:
            raise EntityNotFoundError(
                message=f"Order '{order_id}' not found.", error_code="ORDER_NOT_FOUND"
            )
        if order.customer_profile_id != customer_profile_id:
            raise ForbiddenError(
                message="You do not have access to this order.",
                error_code="ORDER_ACCESS_FORBIDDEN",
            )
        if order.status == "PLACED":
            # Created before payment was required: payable only if it really is still unpaid.
            if await order_is_paid(self.session, order_id):
                raise DomainInvariantError(
                    message="This order has already been paid for.",
                    error_code="ORDER_ALREADY_PAID",
                )
        elif order.status != PENDING_PAYMENT:
            raise DomainInvariantError(
                message=(
                    "This order has expired or was cancelled, so it can't be paid for. "
                    "Please place it again."
                    if order.status == "CANCELLED"
                    else "This order can no longer be paid for."
                ),
                error_code="ORDER_NOT_PAYABLE",
            )
        expected = Decimal(str(order.total_amount)) - Decimal(
            str(order.store_credit_applied or 0)
        )
        if expected <= 0:
            raise DomainInvariantError(
                message="This order has nothing left to pay.",
                error_code="ORDER_NOTHING_TO_PAY",
            )
        if abs(Decimal(str(amount)) - expected) > Decimal("0.01"):
            raise UnprocessableEntityError(
                message=f"The amount to pay for this order is {expected:.2f}.",
                error_code="PAYMENT_AMOUNT_MISMATCH",
            )

    async def _after_capture(self, payment: Payment, new_capture: bool) -> None:
        """The money is in. Show the order to the restaurant (once), then tell the customer.

        If the order was already cancelled (it waited too long and was expired) the restaurant never
        sees it and the customer is not told it is confirmed: what they paid becomes store credit
        instead, like any other cancelled order.
        """
        profile = await self.session.get(CustomerProfile, payment.customer_profile_id)
        placed = await place_paid_order(
            self.session,
            payment.order_id,
            profile.user_id if profile else payment.customer_profile_id,
        )
        if placed == CANCELLED_EARLIER:
            if new_capture:
                await self._credit_late_payment(payment)
            return
        await self._tell_customer_order_is_confirmed(payment.order_id)

    async def _credit_late_payment(self, payment: Payment) -> None:
        order = await self.session.get(Order, payment.order_id)
        if order is None:
            return
        credit = StoreCreditService(self.session)
        await credit.issue(
            customer_profile_id=payment.customer_profile_id,
            brand_id=await credit.brand_id_for_branch(order.branch_id),
            amount=float(payment.amount),
            reason="PAYMENT_AFTER_CANCEL",
        )
        await self.session.commit()
        logger.warning(
            "PaymentAfterOrderCancelled",
            order_id=str(payment.order_id),
            payment_id=str(payment.id),
            amount=float(payment.amount),
        )

    async def create_payment_intent(
        self,
        customer_profile_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: float,
        currency: str = "INR",
    ) -> PaymentIntentResponse:
        await self._check_order_can_be_paid(customer_profile_id, order_id, amount)
        # Create Razorpay order intent via adapter
        rzp_order = await self.razorpay_adapter.create_order(
            amount=amount, currency=currency, receipt=str(order_id)
        )
        razorpay_order_id = rzp_order["id"]

        payment = await self.payment_repo.create_payment_intent(
            order_id=order_id,
            customer_profile_id=customer_profile_id,
            amount=amount,
            currency=currency,
            razorpay_order_id=razorpay_order_id,
        )
        await self.session.commit()
        await self.session.refresh(payment)

        return PaymentIntentResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            razorpay_order_id=razorpay_order_id,
            amount=float(payment.amount),
            currency=payment.currency,
            key_id=settings.RAZORPAY_KEY_ID,
            is_simulated=settings.RAZORPAY_SIMULATE,
        )

    async def verify_payment(self, req: PaymentVerifyRequest) -> PaymentVerifyResponse:
        payment = await self.payment_repo.get_by_order_id(req.order_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment for order '{req.order_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )

        # Validate signature using Razorpay adapter
        is_valid = self.razorpay_adapter.verify_payment_signature(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature,
        )

        if not is_valid:
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="VERIFIED",
                amount=float(payment.amount),
                status="FAILED",
                razorpay_payment_id=req.razorpay_payment_id,
                razorpay_order_id=req.razorpay_order_id,
                razorpay_signature=req.razorpay_signature,
            )
            await self.session.commit()
            raise DomainInvariantError(
                message="Invalid Razorpay HMAC signature.",
                error_code="INVALID_PAYMENT_SIGNATURE",
            )

        # Confirming the same payment twice (a retry, or Razorpay's webhook got there first) must
        # not record the money as captured twice: a cancellation turns "everything captured" into
        # store credit, so a double count would hand out double credit.
        existing = await self.payment_repo.get_transaction_by_razorpay_payment_id(
            req.razorpay_payment_id, transaction_type="CAPTURED"
        )
        new_capture = existing is None or existing.status != "SUCCESS"
        if new_capture:
            # Record VERIFIED transaction
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="VERIFIED",
                amount=float(payment.amount),
                status="SUCCESS",
                razorpay_payment_id=req.razorpay_payment_id,
                razorpay_order_id=req.razorpay_order_id,
                razorpay_signature=req.razorpay_signature,
            )

            # Record CAPTURED transaction
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=float(payment.amount),
                status="SUCCESS",
                razorpay_payment_id=req.razorpay_payment_id,
                razorpay_order_id=req.razorpay_order_id,
            )
            await self.session.commit()

        # Publish PaymentVerifiedEvent
        logger.info(
            "PaymentVerifiedEvent",
            payment_id=str(payment.id),
            order_id=str(payment.order_id),
            razorpay_payment_id=req.razorpay_payment_id,
            amount=float(payment.amount),
            status="CAPTURED",
        )
        await self._after_capture(payment, new_capture)

        return PaymentVerifyResponse(
            success=True,
            payment_id=payment.id,
            order_id=payment.order_id,
            status="CAPTURED",
        )

    async def process_webhook(
        self, raw_body: str | bytes, signature: str
    ) -> dict[str, Any]:
        # Validate webhook signature
        is_valid = self.razorpay_adapter.verify_webhook_signature(raw_body, signature)
        if not is_valid:
            raise DomainInvariantError(
                message="Invalid Razorpay webhook signature.",
                error_code="INVALID_WEBHOOK_SIGNATURE",
            )

        payload_str = (
            raw_body if isinstance(raw_body, str) else raw_body.decode("utf-8")
        )
        event_payload = json.loads(payload_str)
        event_type = event_payload.get("event")
        payload_entity = (
            event_payload.get("payload", {}).get("payment", {}).get("entity", {})
        )

        razorpay_payment_id = payload_entity.get("id")
        razorpay_order_id = payload_entity.get("order_id")
        amount = (
            float(payload_entity.get("amount", 0)) / 100.0
            if payload_entity.get("amount")
            else 0.0
        )

        if razorpay_payment_id:
            # Idempotency check: duplicate webhook
            existing_tx = (
                await self.payment_repo.get_transaction_by_razorpay_payment_id(
                    razorpay_payment_id, transaction_type="CAPTURED"
                )
            )
            if existing_tx:
                logger.info(
                    "Duplicate webhook skipped", razorpay_payment_id=razorpay_payment_id
                )
                return {"status": "ignored", "reason": "DUPLICATE_WEBHOOK"}

        # Find payment by razorpay_order_id or payment_id if present
        payment = None
        if razorpay_order_id:
            # Search payment transactions for matching order_id
            stmt = select(PaymentTransaction).where(
                PaymentTransaction.razorpay_order_id == razorpay_order_id
            )
            res = await self.session.execute(stmt)
            tx = res.scalars().first()
            if tx:
                payment = await self.payment_repo.get_by_id(tx.payment_id)

        if not payment:
            return {"status": "ignored", "reason": "PAYMENT_NOT_FOUND"}

        if event_type == "payment.captured":
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=amount or float(payment.amount),
                status="SUCCESS",
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                payload_snapshot=event_payload,
            )
            await self.session.commit()
            logger.info(
                "PaymentVerifiedEvent", payment_id=str(payment.id), status="CAPTURED"
            )
            await self._after_capture(payment, True)

        elif event_type == "payment.failed":
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=amount or float(payment.amount),
                status="FAILED",
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                payload_snapshot=event_payload,
            )
            await self.session.commit()

        return {"status": "processed", "event": event_type}

    async def refund_payment(
        self, payment_id: uuid.UUID, req: RefundCreateRequest
    ) -> PaymentTransaction:
        ensure_refunds_enabled()
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment '{payment_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )

        # Get latest CAPTURED transaction to obtain razorpay_payment_id
        txs = payment.transactions
        rzp_pay_id = None
        for tx in txs:
            if tx.razorpay_payment_id:
                rzp_pay_id = tx.razorpay_payment_id
                break

        # Execute refund via Razorpay adapter
        refund_res = self.razorpay_adapter.create_refund(
            razorpay_payment_id=rzp_pay_id or "dummy_pay_id",
            amount=req.amount,
        )

        # Append REFUNDED transaction row (enforces INV-PAY-001 cap inside repository)
        refund_tx = await self.payment_repo.append_transaction(
            payment_id=payment_id,
            transaction_type="REFUNDED",
            amount=req.amount,
            status="SUCCESS",
            razorpay_payment_id=rzp_pay_id,
            payload_snapshot={"refund_id": refund_res["id"], "reason": req.reason},
        )
        await self.session.commit()
        await self.session.refresh(refund_tx)
        return refund_tx

    async def get_payment_history(self, payment_id: uuid.UUID) -> Payment:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment '{payment_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )
        return payment
