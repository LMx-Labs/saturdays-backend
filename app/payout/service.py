import hashlib
import json
import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import settings
from app.core.exceptions import (
    DomainInvariantError,
    EntityNotFoundError,
)
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction
from app.payment.razorpay_adapter import RazorpayAdapter
from app.payment.service import ensure_collection_ready
from app.payout.gateway import PayoutGatewayError, RazorpayXClient
from app.payout.models import (
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_PROCESSED,
    PAYOUT_PROCESSING,
    MerchantPayoutAccount,
    Payout,
    PayoutItem,
)
from app.payout.schemas import (
    PayoutDetailResponse,
    PayoutResponse,
    PayoutRunResponse,
    PayoutSkip,
)
from app.subscription.models import MerchantSubscription, PlatformCommission

logger = structlog.get_logger()

_CENT = Decimal("0.01")
_DEFAULT_COMMISSION_RATE = Decimal("5.00")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_ACCOUNT_RE = re.compile(r"^\d{9,18}$")
_ADVISORY_LOCK_KEY = 7_340_011  # arbitrary, app-wide constant

# Razorpay payout status -> our status
_STATUS_MAP = {
    "queued": PAYOUT_PROCESSING,
    "pending": PAYOUT_PROCESSING,
    "scheduled": PAYOUT_PROCESSING,
    "processing": PAYOUT_PROCESSING,
    "processed": PAYOUT_PROCESSED,
    "cancelled": PAYOUT_FAILED,
    "rejected": PAYOUT_FAILED,
    "failed": PAYOUT_FAILED,
    "reversed": PAYOUT_FAILED,
}
MAX_AUTO_ATTEMPTS = 3


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PayoutService:
    def __init__(
        self,
        session: AsyncSession,
        gateway: RazorpayXClient | None = None,
        webhook_verifier: RazorpayAdapter | None = None,
    ):
        self.session = session
        self.gateway = gateway or RazorpayXClient()
        self.webhook_verifier = webhook_verifier or RazorpayAdapter()

    # ------------------------------------------------------------------
    # Daily run
    # ------------------------------------------------------------------

    async def run_daily_payouts(
        self,
        payout_date: date | None = None,
        merchant_id: uuid.UUID | None = None,
        dry_run: bool = False,
    ) -> PayoutRunResponse:
        ensure_collection_ready()
        """Pay every approved merchant what they earned from completed orders.

        Safe to call repeatedly / from several workers: an advisory lock serialises
        runs, each order can only be in one payout (unique constraint), and the
        Razorpay call carries an idempotency key.
        """
        payout_date = payout_date or _utcnow().date()
        locked = await self._try_lock()
        if not locked:
            raise DomainInvariantError(
                message="Another payout run is already in progress.",
                error_code="PAYOUT_RUN_IN_PROGRESS",
            )
        try:
            return await self._run(payout_date, merchant_id, dry_run)
        finally:
            await self._unlock()

    async def _try_lock(self) -> bool:
        if self.session.bind.dialect.name != "postgresql":
            return True
        res = await self.session.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )
        return bool(res.scalar())

    async def _unlock(self) -> None:
        if self.session.bind.dialect.name != "postgresql":
            return
        await self.session.rollback()  # never leave a failed txn holding the session
        await self.session.execute(
            text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )

    async def _run(
        self, payout_date: date, merchant_id: uuid.UUID | None, dry_run: bool
    ) -> PayoutRunResponse:
        payouts: list[Payout] = []
        skipped: list[PayoutSkip] = []
        preview_total = Decimal("0.00")

        # 1. Re-drive payouts that did not reach a final state.
        if not dry_run:
            for payout in await self._retryable_payouts(merchant_id):
                await self._submit(payout)
                payouts.append(payout)

        # 2. Create today's payouts from newly eligible orders.
        by_merchant = await self._eligible_orders_by_merchant(merchant_id)
        for m_id, rows in by_merchant.items():
            merchant: Merchant = rows[0][1]
            problem = self._bank_details_problem(merchant)
            if problem:
                skipped.append(PayoutSkip(merchant_id=m_id, reason=problem))
                continue

            if not dry_run and await self._payout_for(m_id, payout_date):
                # A payout row for this date already exists (any state); new orders
                # roll into the next run rather than mutating it.
                skipped.append(
                    PayoutSkip(
                        merchant_id=m_id,
                        reason="Payout for this date already exists; "
                        "new orders roll into the next run.",
                    )
                )
                continue

            rate = await self._commission_rate(m_id)
            lines = await self._build_lines(rows, rate)
            gross = sum((ln["gross"] for ln in lines), Decimal("0.00"))
            commission = sum((ln["commission"] for ln in lines), Decimal("0.00"))
            net = gross - commission
            if net < _money(settings.PAYOUT_MIN_AMOUNT):
                skipped.append(
                    PayoutSkip(
                        merchant_id=m_id,
                        reason=f"Net amount {net} below minimum payout "
                        f"{settings.PAYOUT_MIN_AMOUNT}; carried over.",
                    )
                )
                continue

            if dry_run:
                preview_total += net
                payouts.append(
                    self._transient_payout(m_id, payout_date, gross, commission, net)
                )
                continue

            payout = Payout(
                merchant_id=m_id,
                payout_date=payout_date,
                gross_amount=gross,
                commission_amount=commission,
                net_amount=net,
                status=PAYOUT_PENDING,
                attempts=0,
                idempotency_key="pending",
            )
            self.session.add(payout)
            await self.session.flush()
            payout.idempotency_key = f"{payout.id}:0"
            for ln in lines:
                if ln["new_commission_for"] is not None:
                    self.session.add(
                        PlatformCommission(
                            order_id=ln["order_id"],
                            merchant_id=m_id,
                            gross_order_amount=ln["gross"],
                            commission_rate_percentage=rate,
                            commission_amount=ln["commission"],
                            merchant_net_payout=ln["gross"] - ln["commission"],
                        )
                    )
                self.session.add(
                    PayoutItem(
                        payout_id=payout.id,
                        order_id=ln["order_id"],
                        gross_amount=ln["gross"],
                        commission_amount=ln["commission"],
                        net_amount=ln["gross"] - ln["commission"],
                    )
                )
            # Commit BEFORE talking to Razorpay: if we crash afterwards the payout
            # is durable and gets re-driven (same idempotency key) next run.
            await self.session.commit()
            await self._submit(payout)
            payouts.append(payout)

        total = (
            preview_total
            if dry_run
            else sum(
                (
                    _money(p.net_amount)
                    for p in payouts
                    if p.status in (PAYOUT_PROCESSING, PAYOUT_PROCESSED)
                ),
                Decimal("0.00"),
            )
        )
        return PayoutRunResponse(
            payout_date=payout_date,
            dry_run=dry_run,
            merchants_paid=len(
                [p for p in payouts if dry_run or p.status != PAYOUT_FAILED]
            ),
            total_net_amount=float(total),
            payouts=[PayoutResponse.model_validate(p) for p in payouts],
            skipped=skipped,
        )

    @staticmethod
    def _transient_payout(
        merchant_id: uuid.UUID,
        payout_date: date,
        gross: Decimal,
        commission: Decimal,
        net: Decimal,
    ) -> Payout:
        return Payout(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            payout_date=payout_date,
            gross_amount=gross,
            commission_amount=commission,
            net_amount=net,
            currency="INR",
            status="DRY_RUN",
            attempts=0,
            idempotency_key="dry-run",
            created_at=_utcnow(),
        )

    async def _payout_for(self, merchant_id: uuid.UUID, d: date) -> Payout | None:
        return (
            await self.session.execute(
                select(Payout).where(
                    Payout.merchant_id == merchant_id, Payout.payout_date == d
                )
            )
        ).scalar_one_or_none()

    async def _retryable_payouts(self, merchant_id: uuid.UUID | None) -> list[Payout]:
        stmt = select(Payout).where(
            (Payout.status == PAYOUT_PENDING)
            | ((Payout.status == PAYOUT_FAILED) & (Payout.attempts < MAX_AUTO_ATTEMPTS))
        )
        if merchant_id:
            stmt = stmt.where(Payout.merchant_id == merchant_id)
        return list((await self.session.execute(stmt)).scalars().all())

    # ------------------------------------------------------------------
    # Eligibility & money math
    # ------------------------------------------------------------------

    async def _eligible_orders_by_merchant(
        self, merchant_id: uuid.UUID | None
    ) -> dict[uuid.UUID, list[tuple[Order, Merchant, Decimal]]]:
        """COMPLETED orders, fully paid, of approved merchants, not yet paid out."""
        cutoff = _utcnow() - timedelta(hours=settings.PAYOUT_SETTLEMENT_DELAY_HOURS)
        stmt = (
            select(Order, Merchant)
            .join(Branch, Branch.id == Order.branch_id)
            .join(Brand, Brand.id == Branch.brand_id)
            .join(Merchant, Merchant.id == Brand.merchant_id)
            .outerjoin(PayoutItem, PayoutItem.order_id == Order.id)
            .where(
                Order.status == "COMPLETED",
                Order.updated_at <= cutoff,
                PayoutItem.id.is_(None),
                Merchant.status == "APPROVED",
                Merchant.deleted_at.is_(None),
            )
            .order_by(Order.created_at)
        )
        if merchant_id:
            stmt = stmt.where(Merchant.id == merchant_id)
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return {}

        order_ids = [o.id for o, _ in rows]
        paid = await self._paid_amounts(order_ids)

        grouped: dict[uuid.UUID, list[tuple[Order, Merchant, Decimal]]] = defaultdict(
            list
        )
        for order, merchant in rows:
            covered = paid.get(order.id, Decimal("0.00")) + _money(
                order.store_credit_applied
            )
            total = _money(order.total_amount)
            if covered < total or total <= 0:
                # Not (fully) paid: never pay a merchant for money we do not hold.
                continue
            # Anything refunded back out reduces what the merchant is owed.
            grouped[merchant.id].append((order, merchant, min(total, covered)))
        return grouped

    async def _paid_amounts(
        self, order_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        signed = case(
            (
                (PaymentTransaction.transaction_type == "CAPTURED")
                & (PaymentTransaction.status == "SUCCESS"),
                PaymentTransaction.amount,
            ),
            (
                (PaymentTransaction.transaction_type == "REFUNDED")
                & (PaymentTransaction.status == "SUCCESS"),
                -PaymentTransaction.amount,
            ),
            else_=0,
        )
        stmt = (
            select(Payment.order_id, func.coalesce(func.sum(signed), 0))
            .join(Payment, Payment.id == PaymentTransaction.payment_id)
            .where(Payment.order_id.in_(order_ids))
            .group_by(Payment.order_id)
        )
        return {
            oid: _money(total)
            for oid, total in (await self.session.execute(stmt)).all()
        }

    async def _commission_rate(self, merchant_id: uuid.UUID) -> Decimal:
        sub = (
            (
                await self.session.execute(
                    select(MerchantSubscription)
                    .where(
                        MerchantSubscription.merchant_id == merchant_id,
                        MerchantSubscription.status == "ACTIVE",
                        MerchantSubscription.valid_until > _utcnow(),
                        MerchantSubscription.deleted_at.is_(None),
                    )
                    .order_by(MerchantSubscription.valid_until.desc())
                )
            )
            .scalars()
            .first()
        )
        return (
            _money(sub.commission_rate_percentage) if sub else _DEFAULT_COMMISSION_RATE
        )

    async def _build_lines(
        self, rows: list[tuple[Order, Merchant, Decimal]], rate: Decimal
    ) -> list[dict[str, Any]]:
        """Per-order gross / commission. Reuses an existing PlatformCommission row
        (immutable ledger) when present; otherwise computes it at today's rate and
        flags it so the ledger row is written together with the payout."""
        order_ids = [o.id for o, _, _ in rows]
        existing = {
            c.order_id: c
            for c in (
                await self.session.execute(
                    select(PlatformCommission).where(
                        PlatformCommission.order_id.in_(order_ids)
                    )
                )
            )
            .scalars()
            .all()
        }
        lines: list[dict[str, Any]] = []
        for order, _merchant, gross in rows:
            comm = existing.get(order.id)
            if comm:
                commission = min(_money(comm.commission_amount), gross)
                new_for = None
            else:
                commission = (gross * rate / Decimal(100)).quantize(
                    _CENT, rounding=ROUND_HALF_UP
                )
                new_for = order.id
            lines.append(
                {
                    "order_id": order.id,
                    "gross": gross,
                    "commission": commission,
                    "new_commission_for": new_for,
                }
            )
        return lines

    @staticmethod
    def _bank_details_problem(merchant: Merchant) -> str | None:
        acct = (merchant.bank_account_number or "").strip()
        ifsc = (merchant.bank_ifsc_code or "").strip().upper()
        if not acct or not ifsc:
            return "Merchant has no bank account details."
        if not _ACCOUNT_RE.match(acct) or not _IFSC_RE.match(ifsc):
            return "Merchant bank account number or IFSC is invalid."
        return None

    # ------------------------------------------------------------------
    # Submitting to Razorpay
    # ------------------------------------------------------------------

    async def _ensure_fund_account(self, merchant: Merchant) -> MerchantPayoutAccount:
        acct = merchant.bank_account_number.strip()
        ifsc = merchant.bank_ifsc_code.strip().upper()
        fingerprint = hashlib.sha256(f"{acct}|{ifsc}".encode()).hexdigest()

        record = (
            await self.session.execute(
                select(MerchantPayoutAccount).where(
                    MerchantPayoutAccount.merchant_id == merchant.id
                )
            )
        ).scalar_one_or_none()
        if record and record.account_fingerprint == fingerprint:
            return record

        contact_id = (
            record.razorpay_contact_id
            if record
            else await self.gateway.create_contact(
                name=merchant.legal_entity_name or merchant.business_name,
                reference_id=str(merchant.id),
            )
        )
        fund_account_id = await self.gateway.create_bank_fund_account(
            contact_id=contact_id,
            name=merchant.legal_entity_name or merchant.business_name,
            ifsc=ifsc,
            account_number=acct,
        )
        if record:  # bank details changed -> new fund account on the same contact
            record.razorpay_fund_account_id = fund_account_id
            record.account_fingerprint = fingerprint
        else:
            record = MerchantPayoutAccount(
                merchant_id=merchant.id,
                razorpay_contact_id=contact_id,
                razorpay_fund_account_id=fund_account_id,
                account_fingerprint=fingerprint,
            )
            self.session.add(record)
        await self.session.commit()
        return record

    async def _submit(self, payout: Payout) -> None:
        """Send one payout to RazorpayX and record the outcome. Never raises."""
        payout_id = str(payout.id)
        try:
            merchant = await self.session.get(Merchant, payout.merchant_id)
            problem = (
                self._bank_details_problem(merchant)
                if merchant
                else "Merchant missing."
            )
            if problem:
                await self._mark_failed(payout, problem, definitive=True)
                return

            account = await self._ensure_fund_account(merchant)
            gp = await self.gateway.create_payout(
                fund_account_id=account.razorpay_fund_account_id,
                amount_paise=int(_money(payout.net_amount) * 100),
                reference_id=str(payout.id),
                narration="Saturdays payout",
                idempotency_key=payout.idempotency_key,
                currency=payout.currency,
            )
        except PayoutGatewayError as exc:
            if exc.retryable:
                # Outcome unknown: keep PENDING + same idempotency key; next run
                # re-sends and Razorpay de-duplicates.
                payout.failure_reason = exc.message
                await self.session.commit()
                logger.warning(
                    "PayoutSubmitRetryable", payout_id=payout_id, error=exc.message
                )
            else:
                await self._mark_failed(payout, exc.message, definitive=True)
            return
        except Exception as exc:
            await self.session.rollback()
            logger.exception("PayoutSubmitUnexpectedError", payout_id=payout_id)
            await self.session.refresh(payout)
            payout.failure_reason = f"Unexpected error: {exc!s}"[:500]
            await self.session.commit()
            return

        payout.razorpay_payout_id = gp.id
        self._apply_status(payout, gp.status, gp.utr, gp.failure_reason)
        await self.session.commit()
        logger.info(
            "PayoutSubmittedEvent",
            payout_id=str(payout.id),
            merchant_id=str(payout.merchant_id),
            status=payout.status,
            amount=float(payout.net_amount),
        )

    async def _mark_failed(self, payout: Payout, reason: str, definitive: bool) -> None:
        payout.status = PAYOUT_FAILED
        payout.failure_reason = reason[:500]
        if definitive:
            payout.attempts += 1
            # New key so a retry is a fresh Razorpay payout, not the cached failure.
            payout.idempotency_key = f"{payout.id}:{payout.attempts}"
        await self.session.commit()
        logger.error(
            "PayoutFailedEvent",
            payout_id=str(payout.id),
            merchant_id=str(payout.merchant_id),
            reason=reason,
        )

    def _apply_status(
        self, payout: Payout, rzp_status: str, utr: str | None, reason: str | None
    ) -> None:
        new_status = _STATUS_MAP.get((rzp_status or "").lower(), PAYOUT_PROCESSING)
        if (
            payout.status == PAYOUT_PROCESSED
            and new_status != PAYOUT_PROCESSED
            and (rzp_status or "").lower() != "reversed"
        ):
            # A processed payout can only go backwards via an explicit reversal.
            return
        payout.status = new_status
        if utr:
            payout.utr = utr
        if new_status == PAYOUT_PROCESSED:
            payout.processed_at = payout.processed_at or _utcnow()
            payout.failure_reason = None
        elif new_status == PAYOUT_FAILED:
            payout.failure_reason = (reason or f"Razorpay status: {rzp_status}")[:500]
            payout.attempts += 1
            payout.idempotency_key = f"{payout.id}:{payout.attempts}"

    # ------------------------------------------------------------------
    # Webhook, retry, queries
    # ------------------------------------------------------------------

    async def process_webhook(self, raw_body: bytes, signature: str) -> dict[str, Any]:
        if not self.webhook_verifier.verify_webhook_signature(raw_body, signature):
            raise DomainInvariantError(
                message="Invalid Razorpay webhook signature.",
                error_code="INVALID_WEBHOOK_SIGNATURE",
            )
        event = json.loads(raw_body.decode("utf-8"))
        event_type: str = event.get("event", "")
        if not event_type.startswith("payout."):
            return {"status": "ignored", "reason": "NOT_A_PAYOUT_EVENT"}

        entity = event.get("payload", {}).get("payout", {}).get("entity", {})
        rzp_id = entity.get("id")
        if not rzp_id:
            return {"status": "ignored", "reason": "NO_PAYOUT_ID"}

        payout = (
            await self.session.execute(
                select(Payout)
                .where(Payout.razorpay_payout_id == rzp_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not payout:
            # Could be a payout we haven't linked yet (timeout race) - match by our reference.
            ref = entity.get("reference_id")
            try:
                payout = await self.session.get(Payout, uuid.UUID(ref)) if ref else None
            except ValueError:
                payout = None
            if not payout:
                return {"status": "ignored", "reason": "PAYOUT_NOT_FOUND"}
            payout.razorpay_payout_id = rzp_id

        status = entity.get("status") or event_type.split(".", 1)[1]
        if payout.status == PAYOUT_FAILED and (status or "").lower() == "failed":
            return {"status": "ignored", "reason": "DUPLICATE_WEBHOOK"}
        self._apply_status(
            payout,
            status,
            entity.get("utr"),
            (entity.get("status_details") or {}).get("description"),
        )
        await self.session.commit()
        logger.info(
            "PayoutWebhookApplied", payout_id=str(payout.id), status=payout.status
        )
        return {"status": "processed", "payout_status": payout.status}

    async def retry_payout(self, payout_id: uuid.UUID) -> PayoutDetailResponse:
        ensure_collection_ready()
        payout = await self._get_payout(payout_id, for_update=True)
        if payout.status not in (PAYOUT_FAILED, PAYOUT_PENDING):
            raise DomainInvariantError(
                message=f"Only FAILED or PENDING payouts can be retried (is {payout.status}).",
                error_code="PAYOUT_NOT_RETRYABLE",
            )
        await self._submit(payout)
        return await self.get_payout(payout_id)

    async def _get_payout(
        self, payout_id: uuid.UUID, for_update: bool = False
    ) -> Payout:
        stmt = (
            select(Payout)
            .where(Payout.id == payout_id)
            .options(selectinload(Payout.items))
        )
        if for_update:
            stmt = stmt.with_for_update()
        payout = (await self.session.execute(stmt)).scalar_one_or_none()
        if not payout:
            raise EntityNotFoundError(
                message=f"Payout '{payout_id}' not found.",
                error_code="PAYOUT_NOT_FOUND",
            )
        return payout

    async def get_payout(
        self, payout_id: uuid.UUID, merchant_id: uuid.UUID | None = None
    ) -> PayoutDetailResponse:
        payout = await self._get_payout(payout_id)
        if merchant_id and payout.merchant_id != merchant_id:
            raise EntityNotFoundError(
                message=f"Payout '{payout_id}' not found.",
                error_code="PAYOUT_NOT_FOUND",
            )
        return PayoutDetailResponse.model_validate(payout)

    async def list_payouts(
        self,
        merchant_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PayoutResponse]:
        stmt = select(Payout).order_by(
            Payout.payout_date.desc(), Payout.created_at.desc()
        )
        if merchant_id:
            stmt = stmt.where(Payout.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(Payout.status == status.upper())
        stmt = stmt.limit(limit).offset(offset)
        return [
            PayoutResponse.model_validate(p)
            for p in (await self.session.execute(stmt)).scalars().all()
        ]
