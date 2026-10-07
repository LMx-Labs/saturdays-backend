import json
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import DomainInvariantError, EntityNotFoundError
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
    ):
        self.session = session
        self.payment_repo = payment_repo
        self.razorpay_adapter = razorpay_adapter or RazorpayAdapter()

    async def create_payment_intent(
        self,
        customer_profile_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: float,
        currency: str = "INR",
    ) -> PaymentIntentResponse:
        # Create Razorpay order intent via adapter
        rzp_order = self.razorpay_adapter.create_order(
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
