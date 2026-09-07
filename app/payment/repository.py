import uuid
from abc import ABC, abstractmethod

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainInvariantError, EntityNotFoundError
from app.payment.models import Payment, PaymentTransaction, PaymentWebhookEvent


class PaymentRepositoryInterface(ABC):
    @abstractmethod
    async def create_payment_intent(
        self,
        order_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        amount: float,
        currency: str = "INR",
        razorpay_order_id: str | None = None,
        provider: str = "mock",
    ) -> Payment:
        pass

    @abstractmethod
    async def get_by_provider_order_id(self, provider_order_id: str) -> Payment | None:
        pass

    @abstractmethod
    async def get_webhook_event(self, provider: str, event_id: str) -> PaymentWebhookEvent | None:
        pass

    @abstractmethod
    async def get_transaction_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentTransaction | None:
        pass

    @abstractmethod
    async def append_transaction(
        self,
        payment_id: uuid.UUID,
        transaction_type: str,
        amount: float,
        status: str,
        razorpay_payment_id: str | None = None,
        razorpay_order_id: str | None = None,
        razorpay_signature: str | None = None,
        payload_snapshot: dict | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentTransaction:
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        pass

    @abstractmethod
    async def get_by_order_id(self, order_id: uuid.UUID) -> Payment | None:
        pass

    @abstractmethod
    async def get_transaction_by_razorpay_payment_id(
        self, razorpay_payment_id: str, transaction_type: str | None = None
    ) -> PaymentTransaction | None:
        pass

    @abstractmethod
    async def get_total_refunded_amount(self, payment_id: uuid.UUID) -> float:
        pass


class PaymentRepository(PaymentRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment_intent(
        self,
        order_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        amount: float,
        currency: str = "INR",
        razorpay_order_id: str | None = None,
        provider: str = "mock",
    ) -> Payment:
        if amount <= 0:
            raise DomainInvariantError(
                message="Payment amount must be greater than zero.",
                error_code="INVALID_PAYMENT_AMOUNT",
            )

        payment = Payment(
            order_id=order_id,
            customer_profile_id=customer_profile_id,
            amount=amount,
            currency=currency,
            provider=provider,
            provider_order_id=razorpay_order_id,
        )
        self.session.add(payment)
        await self.session.flush()

        # Append initial transaction record (INV-0003)
        initial_tx = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="INTENT_CREATED",
            razorpay_order_id=razorpay_order_id,
            amount=amount,
            status="SUCCESS",
            idempotency_key=f"intent:{razorpay_order_id}",
        )
        self.session.add(initial_tx)
        await self.session.flush()

        stmt = (
            select(Payment)
            .where(Payment.id == payment.id)
            .options(selectinload(Payment.transactions))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def append_transaction(
        self,
        payment_id: uuid.UUID,
        transaction_type: str,
        amount: float,
        status: str,
        razorpay_payment_id: str | None = None,
        razorpay_order_id: str | None = None,
        razorpay_signature: str | None = None,
        payload_snapshot: dict | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentTransaction:
        # INV-0003: Append-Only Financial Ledger (no updating existing rows)
        payment = await self.get_by_id(payment_id)
        if not payment:
            raise EntityNotFoundError(
                message=f"Payment with ID '{payment_id}' not found.",
                error_code="PAYMENT_NOT_FOUND",
            )

        # INV-PAY-001: Refund Cap check if transaction_type == "REFUNDED" and status == "SUCCESS"
        if transaction_type == "REFUNDED" and status == "SUCCESS":
            total_refunded = await self.get_total_refunded_amount(payment_id)
            if round(total_refunded + amount, 2) > round(float(payment.amount), 2):
                raise DomainInvariantError(
                    message=f"Refund amount {amount} exceeds original payment total {payment.amount}. Already refunded: {total_refunded}.",
                    error_code="REFUND_EXCEEDS_PAYMENT_AMOUNT",
                )

        tx = PaymentTransaction(
            payment_id=payment_id,
            transaction_type=transaction_type,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_signature=razorpay_signature,
            amount=amount,
            status=status,
            payload_snapshot=payload_snapshot,
            idempotency_key=idempotency_key,
        )
        self.session.add(tx)
        await self.session.flush()
        return tx

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.id == payment_id)
            .options(selectinload(Payment.transactions))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_order_id(self, order_id: uuid.UUID) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .options(selectinload(Payment.transactions))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_provider_order_id(self, provider_order_id: str) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.provider_order_id == provider_order_id)
            .options(selectinload(Payment.transactions))
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_webhook_event(self, provider: str, event_id: str) -> PaymentWebhookEvent | None:
        return await self.session.scalar(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.event_id == event_id,
            )
        )

    async def get_transaction_by_idempotency_key(
        self, idempotency_key: str
    ) -> PaymentTransaction | None:
        return await self.session.scalar(
            select(PaymentTransaction).where(PaymentTransaction.idempotency_key == idempotency_key)
        )

    async def get_transaction_by_razorpay_payment_id(
        self, razorpay_payment_id: str, transaction_type: str | None = None
    ) -> PaymentTransaction | None:
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.razorpay_payment_id == razorpay_payment_id
        )
        if transaction_type:
            stmt = stmt.where(PaymentTransaction.transaction_type == transaction_type)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_total_refunded_amount(self, payment_id: uuid.UUID) -> float:
        stmt = select(func.coalesce(func.sum(PaymentTransaction.amount), 0.0)).where(
            PaymentTransaction.payment_id == payment_id,
            PaymentTransaction.transaction_type == "REFUNDED",
            PaymentTransaction.status == "SUCCESS",
        )
        res = await self.session.execute(stmt)
        return float(res.scalar_one())
