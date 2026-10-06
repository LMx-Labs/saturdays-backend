import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.merchant.models import Merchant
from app.payout.schemas import (
    PayoutDetailResponse,
    PayoutResponse,
    PayoutRunRequest,
    PayoutRunResponse,
)
from app.payout.service import PayoutService

router = APIRouter(prefix="/payouts", tags=["Payouts"])


def get_payout_service(
    session: AsyncSession = Depends(get_db_session),
) -> PayoutService:
    return PayoutService(session=session)


async def _merchant_id_for(session: AsyncSession, user: UserClaims) -> uuid.UUID:
    merchant_id = (
        await session.execute(
            select(Merchant.id).where(
                Merchant.owner_user_id == uuid.UUID(user.sub),
                Merchant.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not merchant_id:
        raise EntityNotFoundError("Merchant profile not found.", "MERCHANT_NOT_FOUND")
    return merchant_id


@router.post(
    "/run",
    response_model=PayoutRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the daily merchant payout batch",
    description=(
        "Pays every approved merchant, from the platform RazorpayX account, the net "
        "amount (gross minus commission) of their completed, fully-paid orders that "
        "have not been paid out yet. Idempotent. Use `dry_run` to preview."
    ),
)
async def run_payouts(
    req: PayoutRunRequest,
    _admin: UserClaims = Depends(require_role(["PlatformAdmin"])),
    service: PayoutService = Depends(get_payout_service),
) -> PayoutRunResponse:
    return await service.run_daily_payouts(
        payout_date=req.payout_date, merchant_id=req.merchant_id, dry_run=req.dry_run
    )


@router.get(
    "",
    response_model=list[PayoutResponse],
    summary="List payouts (PlatformAdmin)",
)
async def list_payouts(
    merchant_id: uuid.UUID | None = Query(None),
    payout_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: UserClaims = Depends(require_role(["PlatformAdmin"])),
    service: PayoutService = Depends(get_payout_service),
) -> list[PayoutResponse]:
    return await service.list_payouts(
        merchant_id=merchant_id, status=payout_status, limit=limit, offset=offset
    )


@router.get(
    "/me",
    response_model=list[PayoutResponse],
    summary="List my restaurant's payouts (MerchantOwner)",
)
async def list_my_payouts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserClaims = Depends(require_role(["MerchantOwner"])),
    session: AsyncSession = Depends(get_db_session),
    service: PayoutService = Depends(get_payout_service),
) -> list[PayoutResponse]:
    return await service.list_payouts(
        merchant_id=await _merchant_id_for(session, current_user),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/me/{payout_id}",
    response_model=PayoutDetailResponse,
    summary="My payout with the orders it settles (MerchantOwner)",
)
async def get_my_payout(
    payout_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(["MerchantOwner"])),
    session: AsyncSession = Depends(get_db_session),
    service: PayoutService = Depends(get_payout_service),
) -> PayoutDetailResponse:
    return await service.get_payout(
        payout_id, merchant_id=await _merchant_id_for(session, current_user)
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="RazorpayX payout webhook",
    description="Updates payout status (processed / failed / reversed) from RazorpayX.",
)
async def payout_webhook(
    request: Request,
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature"),
    service: PayoutService = Depends(get_payout_service),
) -> dict[str, Any]:
    return await service.process_webhook(await request.body(), x_razorpay_signature)


@router.get(
    "/{payout_id}",
    response_model=PayoutDetailResponse,
    summary="Payout detail (PlatformAdmin)",
)
async def get_payout(
    payout_id: uuid.UUID,
    _admin: UserClaims = Depends(require_role(["PlatformAdmin"])),
    service: PayoutService = Depends(get_payout_service),
) -> PayoutDetailResponse:
    return await service.get_payout(payout_id)


@router.post(
    "/{payout_id}/retry",
    response_model=PayoutDetailResponse,
    summary="Retry a failed payout (PlatformAdmin)",
)
async def retry_payout(
    payout_id: uuid.UUID,
    _admin: UserClaims = Depends(require_role(["PlatformAdmin"])),
    service: PayoutService = Depends(get_payout_service),
) -> PayoutDetailResponse:
    return await service.retry_payout(payout_id)
