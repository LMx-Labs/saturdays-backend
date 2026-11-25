"""QR code and payment link endpoints.

Admin:    GET /api/v1/admin/merchants/{id}/qr-codes
Merchant: GET /api/v1/merchants/me/qr-codes
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository
from app.subscription.models import MerchantSubscription
from app.subscription.razorpay_service import create_registration_payment_link

router = APIRouter(tags=["QR Codes"])
logger = structlog.get_logger()


class QRCodeResponse(BaseModel):
    merchant_id: str
    registration_fee_paid: bool
    registration_fee_payment_link: str | None
    registration_fee_qr_url: str | None
    is_trial: bool
    trial_ends_at: str | None
    plan_tier: str | None
    plan_payment_link: str | None


async def _build_qr_response(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    merchant_name: str,
    *,
    generate_link_if_missing: bool = False,
) -> QRCodeResponse:
    result = await session.execute(
        select(MerchantSubscription)
        .where(MerchantSubscription.merchant_id == merchant_id)
        .order_by(MerchantSubscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()

    reg_link: str | None = None
    reg_qr: str | None = None

    if sub and not sub.registration_fee_paid:
        if sub.razorpay_payment_link_id:
            reg_link = f"https://rzp.io/l/{sub.razorpay_payment_link_id}"
        elif generate_link_if_missing:
            try:
                link_data = await create_registration_payment_link(
                    str(merchant_id), merchant_name
                )
                reg_link = link_data.get("short_url")
                link_id = link_data.get("id")
                if link_id:
                    sub.razorpay_payment_link_id = link_id
                    await session.commit()
            except Exception as exc:
                logger.warning("Could not create reg fee link", error=str(exc))

    return QRCodeResponse(
        merchant_id=str(merchant_id),
        registration_fee_paid=sub.registration_fee_paid if sub else False,
        registration_fee_payment_link=reg_link,
        registration_fee_qr_url=reg_qr,
        is_trial=sub.is_trial if sub else False,
        trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
        plan_tier=sub.plan_tier if sub else None,
        plan_payment_link=None,
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
    """Admin: fetch (and generate if missing) QR/payment link for a merchant."""
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


@router.get(
    "/merchants/me/qr-codes",
    response_model=QRCodeResponse,
)
async def merchant_get_own_qr_codes(
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QRCodeResponse:
    """Restaurant: get own QR codes and subscription status."""
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
        session, merchant.id, merchant_name, generate_link_if_missing=False
    )
