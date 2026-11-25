"""Razorpay webhook handler.

Registered at POST /webhooks/razorpay (no API prefix — public endpoint).
Verifies Razorpay HMAC-SHA256 signature, enforces idempotency via
razorpay_webhook_events, then processes subscription lifecycle events.
"""
import json
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.subscription.models import MerchantSubscription, RazorpayWebhookEvent
from app.subscription.razorpay_service import verify_webhook_signature
from app.subscription.repository import SubscriptionRepository

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = structlog.get_logger()


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    body = await request.body()

    # --- Signature verification ---
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if webhook_secret and x_razorpay_signature:
        if not verify_webhook_signature(body, x_razorpay_signature, webhook_secret):
            logger.warning("Razorpay webhook signature mismatch")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload: dict = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_id: str = payload.get("id") or str(uuid.uuid4())
    event_type: str = payload.get("event", "unknown")

    # --- Idempotency ---
    existing = await session.execute(
        select(RazorpayWebhookEvent).where(RazorpayWebhookEvent.event_id == event_id)
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate webhook, skipping", event_id=event_id)
        return {"status": "duplicate"}

    # Record event immediately
    webhook_record = RazorpayWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(webhook_record)

    # --- Event handling ---
    sub_repo = SubscriptionRepository(session=session)
    entity_payload: dict = payload.get("payload", {})

    async def _find_sub_by_razorpay_id(rzp_sub_id: str) -> MerchantSubscription | None:
        result = await session.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.razorpay_subscription_id == rzp_sub_id
            )
        )
        return result.scalar_one_or_none()

    if event_type == "subscription.charged":
        rzp_sub = entity_payload.get("subscription", {}).get("entity", {})
        rzp_sub_id = rzp_sub.get("id")
        if rzp_sub_id:
            sub = await _find_sub_by_razorpay_id(rzp_sub_id)
            if sub:
                now = datetime.now(UTC)
                current_expiry = (
                    sub.valid_until.replace(tzinfo=UTC)
                    if sub.valid_until.tzinfo is None
                    else sub.valid_until
                )
                new_expiry = max(now, current_expiry) + timedelta(days=30)
                await sub_repo.update_subscription(sub, {
                    "status": "ACTIVE",
                    "valid_until": new_expiry,
                    "is_trial": False,
                })
                logger.info(
                    "subscription.charged — extended",
                    merchant_id=str(sub.merchant_id),
                    new_expiry=new_expiry.isoformat(),
                )

    elif event_type == "subscription.activated":
        rzp_sub = entity_payload.get("subscription", {}).get("entity", {})
        rzp_sub_id = rzp_sub.get("id")
        if rzp_sub_id:
            sub = await _find_sub_by_razorpay_id(rzp_sub_id)
            if sub:
                await sub_repo.update_subscription(sub, {
                    "status": "ACTIVE",
                    "is_trial": False,
                })
                logger.info("subscription.activated", merchant_id=str(sub.merchant_id))

    elif event_type == "subscription.cancelled":
        rzp_sub = entity_payload.get("subscription", {}).get("entity", {})
        rzp_sub_id = rzp_sub.get("id")
        if rzp_sub_id:
            sub = await _find_sub_by_razorpay_id(rzp_sub_id)
            if sub:
                await sub_repo.update_subscription(sub, {"status": "CANCELLED"})
                logger.info("subscription.cancelled", merchant_id=str(sub.merchant_id))

    elif event_type == "subscription.halted":
        rzp_sub = entity_payload.get("subscription", {}).get("entity", {})
        rzp_sub_id = rzp_sub.get("id")
        if rzp_sub_id:
            sub = await _find_sub_by_razorpay_id(rzp_sub_id)
            if sub:
                await sub_repo.update_subscription(sub, {"status": "EXPIRED"})
                logger.warning("subscription.halted", merchant_id=str(sub.merchant_id))

    elif event_type == "payment.captured":
        # Could be the ₹500 registration fee
        payment_entity: dict = entity_payload.get("payment", {}).get("entity", {})
        notes: dict = payment_entity.get("notes", {})
        if notes.get("type") == "REGISTRATION_FEE":
            merchant_id_str: str | None = notes.get("merchant_id")
            payment_id: str | None = payment_entity.get("id")
            if merchant_id_str:
                try:
                    merchant_uuid = uuid.UUID(merchant_id_str)
                    result = await session.execute(
                        select(MerchantSubscription)
                        .where(MerchantSubscription.merchant_id == merchant_uuid)
                        .order_by(MerchantSubscription.created_at.desc())
                    )
                    sub = result.scalar_one_or_none()
                    if sub:
                        now = datetime.now(UTC)
                        trial_end = now + timedelta(days=7)
                        await sub_repo.update_subscription(sub, {
                            "registration_fee_paid": True,
                            "registration_fee_payment_id": payment_id,
                            "is_trial": True,
                            "trial_ends_at": trial_end,
                            "status": "TRIAL",
                            "valid_until": trial_end,
                        })
                        logger.info(
                            "Registration fee paid — trial started",
                            merchant_id=merchant_id_str,
                            trial_end=trial_end.isoformat(),
                        )
                except ValueError:
                    logger.error("Invalid merchant_id in webhook", merchant_id=merchant_id_str)

    await session.commit()
    return {"status": "ok", "event": event_type}
