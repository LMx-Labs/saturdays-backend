"""QR code and payment link endpoints.

Admin:    GET /api/v1/admin/merchants/{id}/qr-codes
          POST /api/v1/admin/merchants/{id}/refresh-qr-codes
Merchant: GET /api/v1/merchants/me/qr-codes
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository
from app.subscription.models import MerchantSubscription, SubscriptionPlanConfig
from app.subscription.repository import SubscriptionRepository
from app.subscription.razorpay_service import (
    create_razorpay_subscription,
    create_registration_payment_link,
    create_subscription_payment_link,
)

router = APIRouter(tags=["QR Codes"])
logger = structlog.get_logger()

PLAN_DEFAULT_NAMES = {
    "BASIC": "Campus Starter",
    "PROFESSIONAL": "Growth Multi-Store",
    "ENTERPRISE": "Campus Franchise",
}

PLAN_DEFAULT_PRICES = {
    "BASIC": 999,
    "PROFESSIONAL": 2499,
    "ENTERPRISE": 4999,
}


class QRCodeResponse(BaseModel):
    merchant_id: str
    registration_fee_paid: bool
    registration_fee_payment_link: str | None = None
    registration_payment_link: str | None = None  # Admin alias
    registration_fee_qr_url: str | None = None
    registration_qr_url: str | None = None  # Admin alias
    is_trial: bool = False
    trial_ends_at: str | None = None
    plan_tier: str | None = None
    plan_name: str | None = None
    plan_payment_link: str | None = None
    subscription_payment_link: str | None = None  # Admin alias
    plan_qr_url: str | None = None
    subscription_qr_url: str | None = None  # Admin alias


async def _build_qr_response(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    merchant_name: str,
    *,
    generate_link_if_missing: bool = False,
    force_refresh: bool = False,
) -> QRCodeResponse:
    sub_repo = SubscriptionRepository(session=session)
    sub = await sub_repo.get_active_subscription(merchant_id)
    if not sub:
        result = await session.execute(
            select(MerchantSubscription)
            .where(
                MerchantSubscription.merchant_id == merchant_id,
                MerchantSubscription.deleted_at.is_(None),
            )
            .order_by(MerchantSubscription.created_at.desc())
            .limit(1)
        )
        sub = result.scalars().first()

    reg_link: str | None = None
    reg_qr: str | None = None
    plan_link: str | None = None
    plan_qr: str | None = None
    plan_name: str | None = None

    if sub:
        tier = (sub.plan_tier or "BASIC").upper()
        plan_name = PLAN_DEFAULT_NAMES.get(tier, tier)

        # Look up DB plan config for custom name / price / razorpay_plan_id
        plan_cfg_res = await session.execute(
            select(SubscriptionPlanConfig).where(SubscriptionPlanConfig.tier == tier)
        )
        plan_cfg = plan_cfg_res.scalar_one_or_none()
        if plan_cfg:
            plan_name = plan_cfg.name
            plan_price = plan_cfg.price_monthly
            rzp_plan_id = plan_cfg.razorpay_plan_id
        else:
            plan_price = PLAN_DEFAULT_PRICES.get(tier, 999)
            rzp_plan_id = None

        has_changed = False

        # --- 1. Registration Fee Link & QR ---
        if not sub.registration_fee_paid:
            if not force_refresh and sub.razorpay_payment_link_id and sub.registration_fee_qr_url:
                reg_link = f"https://rzp.io/l/{sub.razorpay_payment_link_id}" if not sub.razorpay_payment_link_id.startswith("http") else sub.razorpay_payment_link_id
                reg_qr = sub.registration_fee_qr_url
            elif generate_link_if_missing or force_refresh:
                try:
                    link_data = await create_registration_payment_link(
                        str(merchant_id), merchant_name
                    )
                    reg_link = link_data.get("short_url")
                    reg_qr = link_data.get("qr_code_url")
                    link_id = link_data.get("id")
                    if link_id:
                        sub.razorpay_payment_link_id = link_id
                    if reg_qr:
                        sub.registration_fee_qr_url = reg_qr
                    has_changed = True
                except Exception as exc:
                    logger.warning("Could not create registration fee link", error=str(exc))

        # --- 2. Subscription Plan Link & QR ---
        if not force_refresh and sub.plan_payment_link and sub.plan_qr_url:
            plan_link = sub.plan_payment_link
            plan_qr = sub.plan_qr_url
        elif generate_link_if_missing or force_refresh:
            try:
                # First attempt: recurring subscription via Razorpay plan_id
                if rzp_plan_id:
                    sub_data = await create_razorpay_subscription(rzp_plan_id)
                    plan_link = sub_data.get("short_url")
                    plan_qr = sub_data.get("qr_code_url")
                    rzp_sub_id = sub_data.get("id")
                    if rzp_sub_id:
                        sub.razorpay_subscription_id = rzp_sub_id
                else:
                    sub_data = {}

                # Second attempt / fallback: standard payment link for plan fee
                if not plan_link:
                    plink_data = await create_subscription_payment_link(
                        str(merchant_id), merchant_name, tier, plan_name, plan_price
                    )
                    plan_link = plink_data.get("short_url")
                    plan_qr = plink_data.get("qr_code_url")

                if plan_link:
                    sub.plan_payment_link = plan_link
                if plan_qr:
                    sub.plan_qr_url = plan_qr
                has_changed = True
            except Exception as exc:
                logger.warning("Could not create plan subscription link", error=str(exc))

        if has_changed:
            await session.commit()
            await session.refresh(sub)

    return QRCodeResponse(
        merchant_id=str(merchant_id),
        registration_fee_paid=sub.registration_fee_paid if sub else False,
        registration_fee_payment_link=reg_link,
        registration_payment_link=reg_link,
        registration_fee_qr_url=reg_qr,
        registration_qr_url=reg_qr,
        is_trial=sub.is_trial if sub else False,
        trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
        plan_tier=sub.plan_tier if sub else None,
        plan_name=plan_name,
        plan_payment_link=plan_link,
        subscription_payment_link=plan_link,
        plan_qr_url=plan_qr,
        subscription_qr_url=plan_qr,
    )


@router.get(
    "/admin/merchants/{merchant_id}/qr-codes",
    response_model=QRCodeResponse,
)
async def admin_get_merchant_qr_codes(
    merchant_id: str,
    _: UserClaims = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> QRCodeResponse:
    """Admin: fetch (and auto-generate if missing) QR codes and payment links for a merchant."""
    try:
        merchant_uuid = uuid.UUID(merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant_id")

    merchant_repo = MerchantRepository(session=session)
    merchant = await merchant_repo.get_by_id(merchant_uuid)
    merchant_name = (
        getattr(merchant, "business_name", None)
        or getattr(merchant, "legal_entity_name", None)
        or "Restaurant"
        if merchant
        else "Restaurant"
    )
    return await _build_qr_response(
        session, merchant_uuid, merchant_name, generate_link_if_missing=True
    )


@router.post(
    "/admin/merchants/{merchant_id}/refresh-qr-codes",
    response_model=QRCodeResponse,
    status_code=status.HTTP_200_OK,
)
async def admin_refresh_merchant_qr_codes(
    merchant_id: str,
    _: UserClaims = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> QRCodeResponse:
    """Admin: force regenerate Razorpay payment links and QR codes for a merchant."""
    try:
        merchant_uuid = uuid.UUID(merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant_id")

    merchant_repo = MerchantRepository(session=session)
    merchant = await merchant_repo.get_by_id(merchant_uuid)
    merchant_name = (
        getattr(merchant, "business_name", None)
        or getattr(merchant, "legal_entity_name", None)
        or "Restaurant"
        if merchant
        else "Restaurant"
    )
    return await _build_qr_response(
        session, merchant_uuid, merchant_name, generate_link_if_missing=True, force_refresh=True
    )


@router.get(
    "/merchants/me/qr-codes",
    response_model=QRCodeResponse,
)
async def merchant_get_own_qr_codes(
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QRCodeResponse:
    """Restaurant: get own QR codes and subscription status (auto-generates if missing)."""
    merchant_repo = MerchantRepository(session=session)
    merchant = await merchant_repo.get_by_owner_user_id(uuid.UUID(current_user.sub))
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant_name = (
        getattr(merchant, "business_name", None)
        or getattr(merchant, "legal_entity_name", None)
        or "Restaurant"
    )
    return await _build_qr_response(
        session, merchant.id, merchant_name, generate_link_if_missing=True
    )
