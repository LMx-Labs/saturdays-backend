import hashlib
import hmac
import json
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainInvariantError, EntityNotFoundError, ForbiddenError
from app.inventory.models import InventoryItem, InventoryLog
from app.order.models import Order, StockReservation
from app.payment.models import Payment, PaymentTransaction, PaymentWebhookEvent
from app.payment.razorpay_adapter import PaymentGateway, get_payment_gateway
from app.payment.repository import PaymentRepositoryInterface
from app.payment.schemas import (
    PaymentIntentResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    RefundCreateRequest,
)

logger = structlog.get_logger()


class PaymentServiceInterface(ABC):
    @abstractmethod
    async def create_payment_intent(
        self,
        customer_profile_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: float | None = None,
        currency: str | None = None,
    ) -> PaymentIntentResponse:
        pass

    @abstractmethod
    async def verify_payment(
        self, req: PaymentVerifyRequest, customer_profile_id: uuid.UUID
    ) -> PaymentVerifyResponse:
        pass

    @abstractmethod
    async def complete_mock_payment(
        self, order_id: uuid.UUID, customer_profile_id: uuid.UUID
    ) -> PaymentVerifyResponse:
        pass

    @abstractmethod
    async def process_webhook(self, raw_body: str | bytes, signature: str) -> dict[str, Any]:
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
        razorpay_adapter: PaymentGateway | None = None,
    ):
        self.session = session
        self.payment_repo = payment_repo
        self.gateway = razorpay_adapter or get_payment_gateway()

    async def create_payment_intent(
        self,
        customer_profile_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: float | None = None,
        currency: str | None = None,
    ) -> PaymentIntentResponse:
        order = await self.session.get(Order, order_id)
        if not order:
            raise EntityNotFoundError("Order not found.", "ORDER_NOT_FOUND")
        if order.customer_profile_id != customer_profile_id:
            raise ForbiddenError("Order does not belong to customer.", "ORDER_ACCESS_FORBIDDEN")
        if order.status not in {"PLACED", "ACCEPTED"}:
            raise DomainInvariantError("Order is not eligible for payment.", "ORDER_NOT_PAYABLE")
        existing = await self.payment_repo.get_by_order_id(order_id)
        if existing:
            return PaymentIntentResponse(
                payment_id=existing.id,
                order_id=existing.order_id,
                razorpay_order_id=existing.provider_order_id or "",
                amount=float(existing.amount),
                currency=existing.currency,
                provider=existing.provider,
                provider_key_id=getattr(self.gateway, "key_id", None),
            )
        server_amount = float(order.total_amount)
        server_currency = order.currency
        rzp_order = self.gateway.create_order(
            amount=server_amount, currency=server_currency, receipt=str(order_id)
        )
        razorpay_order_id = rzp_order["id"]

        payment = await self.payment_repo.create_payment_intent(
            order_id=order_id,
            customer_profile_id=customer_profile_id,
            amount=server_amount,
            currency=server_currency,
            razorpay_order_id=razorpay_order_id,
            provider=self.gateway.provider,
        )
        await self.session.commit()
        await self.session.refresh(payment)

        return PaymentIntentResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            razorpay_order_id=razorpay_order_id,
            amount=float(payment.amount),
            currency=payment.currency,
            provider=self.gateway.provider,
            provider_key_id=getattr(self.gateway, "key_id", None),
        )

    async def complete_mock_payment(
        self, order_id: uuid.UUID, customer_profile_id: uuid.UUID
    ) -> PaymentVerifyResponse:
        if self.gateway.provider != "mock":
            raise ForbiddenError("Mock checkout is not enabled.", "MOCK_PAYMENT_DISABLED")
        payment = await self.payment_repo.get_by_order_id(order_id)
        if not payment or payment.customer_profile_id != customer_profile_id:
            raise EntityNotFoundError("Payment not found.", "PAYMENT_NOT_FOUND")
        provider_order_id = payment.provider_order_id or ""
        provider_payment_id = f"pay_mock_{hashlib.sha256(str(order_id).encode()).hexdigest()[:16]}"
        key_secret = getattr(self.gateway, "key_secret", "")
        signature = hmac.new(
            key_secret.encode(),
            f"{provider_order_id}|{provider_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return await self.verify_payment(
            PaymentVerifyRequest(
                order_id=order_id,
                razorpay_order_id=provider_order_id,
                razorpay_payment_id=provider_payment_id,
                razorpay_signature=signature,
            ),
            customer_profile_id,
        )

    async def verify_payment(
        self, req: PaymentVerifyRequest, customer_profile_id: uuid.UUID
    ) -> PaymentVerifyResponse:
        payment = await self.payment_repo.get_by_order_id(req.order_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment for order '{req.order_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )
        if payment.customer_profile_id != customer_profile_id:
            raise ForbiddenError("Payment access denied.", "PAYMENT_ACCESS_FORBIDDEN")
        if payment.provider_order_id != req.razorpay_order_id:
            raise DomainInvariantError(
                "Payment intent does not match provider order.",
                "PAYMENT_INTENT_MISMATCH",
            )
        existing = await self.payment_repo.get_transaction_by_razorpay_payment_id(
            req.razorpay_payment_id, transaction_type="CAPTURED"
        )
        if existing:
            if existing.payment_id != payment.id:
                raise DomainInvariantError(
                    "Provider payment is linked to another order.",
                    "PROVIDER_PAYMENT_MISMATCH",
                )
            return PaymentVerifyResponse(
                success=True,
                payment_id=payment.id,
                order_id=payment.order_id,
                status="CAPTURED",
            )

        is_valid = self.gateway.verify_payment_signature(
            provider_order_id=req.razorpay_order_id,
            provider_payment_id=req.razorpay_payment_id,
            signature=req.razorpay_signature,
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
                idempotency_key=f"verify-failed:{payment.id}:{req.razorpay_payment_id}",
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
            idempotency_key=f"verify:{payment.id}:{req.razorpay_payment_id}",
        )

        # Record CAPTURED transaction
        await self.payment_repo.append_transaction(
            payment_id=payment.id,
            transaction_type="CAPTURED",
            amount=float(payment.amount),
            status="SUCCESS",
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_order_id=req.razorpay_order_id,
            idempotency_key=f"capture:{payment.id}:{req.razorpay_payment_id}",
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

    async def process_webhook(self, raw_body: str | bytes, signature: str) -> dict[str, Any]:
        # Validate webhook signature
        is_valid = self.gateway.verify_webhook_signature(raw_body, signature)
        if not is_valid:
            raise DomainInvariantError(
                message="Invalid Razorpay webhook signature.",
                error_code="INVALID_WEBHOOK_SIGNATURE",
            )

        payload_str = raw_body if isinstance(raw_body, str) else raw_body.decode("utf-8")
        event_payload = json.loads(payload_str)
        event_type = event_payload.get("event")
        event_id = event_payload.get("id") or hashlib.sha256(payload_str.encode()).hexdigest()
        if await self.payment_repo.get_webhook_event(self.gateway.provider, event_id):
            return {"status": "ignored", "reason": "DUPLICATE_WEBHOOK"}
        payload_entity = event_payload.get("payload", {}).get("payment", {}).get("entity", {})

        razorpay_payment_id = payload_entity.get("id")
        razorpay_order_id = payload_entity.get("order_id")
        amount = (
            float(payload_entity.get("amount", 0)) / 100.0 if payload_entity.get("amount") else 0.0
        )

        if razorpay_payment_id:
            existing_tx = await self.payment_repo.get_transaction_by_razorpay_payment_id(
                razorpay_payment_id, transaction_type="CAPTURED"
            )
            if existing_tx:
                logger.info("Duplicate webhook skipped", razorpay_payment_id=razorpay_payment_id)
                return {"status": "ignored", "reason": "DUPLICATE_WEBHOOK"}

        payment = (
            await self.payment_repo.get_by_provider_order_id(razorpay_order_id)
            if razorpay_order_id
            else None
        )

        if not payment:
            return {"status": "ignored", "reason": "PAYMENT_NOT_FOUND"}
        if amount and round(amount, 2) != round(float(payment.amount), 2):
            raise DomainInvariantError(
                "Webhook amount does not match payment intent.",
                "WEBHOOK_AMOUNT_MISMATCH",
            )
        self.session.add(
            PaymentWebhookEvent(
                provider=self.gateway.provider,
                event_id=event_id,
                event_type=event_type or "unknown",
                payload_snapshot=event_payload,
            )
        )

        if event_type == "payment.captured":
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=amount or float(payment.amount),
                status="SUCCESS",
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                payload_snapshot=event_payload,
                idempotency_key=f"webhook:{event_id}",
            )
            await self.session.commit()
            logger.info("PaymentVerifiedEvent", payment_id=str(payment.id), status="CAPTURED")

        elif event_type == "payment.failed":
            await self.payment_repo.append_transaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=amount or float(payment.amount),
                status="FAILED",
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                payload_snapshot=event_payload,
                idempotency_key=f"webhook:{event_id}",
            )
            await self.session.commit()

        return {"status": "processed", "event": event_type}

    async def refund_payment(
        self, payment_id: uuid.UUID, req: RefundCreateRequest
    ) -> PaymentTransaction:
        ledger_key = f"refund:{payment_id}:{req.idempotency_key}" if req.idempotency_key else None
        if ledger_key:
            existing_refund = await self.payment_repo.get_transaction_by_idempotency_key(ledger_key)
            if existing_refund:
                return existing_refund
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment '{payment_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )

        # Get latest CAPTURED transaction to obtain razorpay_payment_id
        txs = payment.transactions
        if not any(tx.transaction_type == "CAPTURED" and tx.status == "SUCCESS" for tx in txs):
            raise DomainInvariantError(
                "Only captured payments can be refunded.",
                "PAYMENT_NOT_REFUNDABLE",
            )
        rzp_pay_id = None
        for tx in txs:
            if tx.razorpay_payment_id:
                rzp_pay_id = tx.razorpay_payment_id
                break

        # Execute refund via Razorpay adapter
        refund_res = self.gateway.create_refund(
            provider_payment_id=rzp_pay_id or payment.provider_order_id or "mock_payment",
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
            idempotency_key=ledger_key or f"refund:{uuid.uuid4()}",
        )
        await self._restore_cancelled_order_stock(payment.order_id)
        await self.session.commit()
        await self.session.refresh(refund_tx)
        return refund_tx

    async def _restore_cancelled_order_stock(self, order_id: uuid.UUID) -> None:
        order = await self.session.get(Order, order_id)
        if not order or order.status != "CANCELLED":
            return
        reservations = (
            await self.session.execute(
                select(StockReservation)
                .where(
                    StockReservation.order_id == order_id,
                    StockReservation.status == "RESERVED",
                )
                .with_for_update()
            )
        ).scalars()
        for reservation in reservations:
            inventory = await self.session.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == reservation.inventory_item_id)
                .with_for_update()
            )
            if not inventory:
                continue
            previous = inventory.quantity
            inventory.quantity += reservation.quantity
            inventory.is_in_stock = True
            reservation.status = "RESTORED"
            reservation.restored_at = datetime.now(UTC)
            self.session.add(
                InventoryLog(
                    inventory_item_id=inventory.id,
                    change_amount=reservation.quantity,
                    previous_quantity=previous,
                    new_quantity=inventory.quantity,
                    reason=f"PAYMENT_REFUND_CANCELLED_ORDER:{order_id}",
                )
            )

    async def get_payment_history(self, payment_id: uuid.UUID) -> Payment:
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment '{payment_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )
        return payment
