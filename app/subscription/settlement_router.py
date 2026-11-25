"""Admin settlement cycle management + transaction history.

Registered at /api/v1/admin/settlements
"""
import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository
from app.subscription.models import MerchantSettlement, MerchantSubscription

router = APIRouter(prefix="/admin/settlements", tags=["Admin — Settlements"])
logger = structlog.get_logger()


class SettlementCycleRequest(BaseModel):
    settlement_cycle_days: Literal[1, 3, 7]


class SettlementCycleResponse(BaseModel):
    merchant_id: str
    settlement_cycle_days: int
    updated_at: str


class SettlementResponse(BaseModel):
    id: str
    merchant_id: str
    merchant_name: str | None
    settlement_id: str | None
    gross_amount: float
    commission_deducted: float
    net_amount: float
    status: str
    settlement_date: str | None
    created_at: str


@router.patch(
    "/merchants/{merchant_id}/cycle",
    response_model=SettlementCycleResponse,
    status_code=status.HTTP_200_OK,
)
async def update_settlement_cycle(
    merchant_id: str,
    req: SettlementCycleRequest,
    _: UserClaims = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> SettlementCycleResponse:
    """Toggle settlement cycle for a merchant: 1=daily, 3=every 3 days, 7=weekly."""
    try:
        merchant_uuid = uuid.UUID(merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant_id")

    result = await session.execute(
        select(MerchantSubscription)
        .where(MerchantSubscription.merchant_id == merchant_uuid)
        .where(MerchantSubscription.status.in_(["ACTIVE", "TRIAL"]))
        .order_by(MerchantSubscription.created_at.desc())
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=404, detail="No active subscription found for this merchant"
        )

    sub.settlement_cycle_days = req.settlement_cycle_days
    await session.commit()
    logger.info(
        "Settlement cycle updated",
        merchant_id=merchant_id,
        days=req.settlement_cycle_days,
    )
    return SettlementCycleResponse(
        merchant_id=merchant_id,
        settlement_cycle_days=req.settlement_cycle_days,
        updated_at=datetime.now(UTC).isoformat(),
    )


@router.get("", response_model=list[SettlementResponse], status_code=status.HTTP_200_OK)
async def list_settlements(
    merchant_id: str | None = Query(default=None),
    settlement_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    skip: int = Query(default=0),
    _: UserClaims = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> list[SettlementResponse]:
    """List all settlements; filterable by merchant or status."""
    query = (
        select(MerchantSettlement)
        .order_by(desc(MerchantSettlement.created_at))
        .offset(skip)
        .limit(limit)
    )
    if merchant_id:
        try:
            query = query.where(MerchantSettlement.merchant_id == uuid.UUID(merchant_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid merchant_id")
    if settlement_status:
        query = query.where(MerchantSettlement.status == settlement_status.upper())

    result = await session.execute(query)
    settlements = result.scalars().all()

    merchant_repo = MerchantRepository(session=session)
    responses: list[SettlementResponse] = []
    for s in settlements:
        merchant = await merchant_repo.get_by_id(s.merchant_id)
        merchant_name: str | None = None
        if merchant:
            merchant_name = (
                getattr(merchant, "business_name", None)
                or getattr(merchant, "legal_entity_name", None)
            )
        responses.append(
            SettlementResponse(
                id=str(s.id),
                merchant_id=str(s.merchant_id),
                merchant_name=merchant_name,
                settlement_id=s.settlement_id,
                gross_amount=float(s.gross_amount),
                commission_deducted=float(s.commission_deducted),
                net_amount=float(s.net_amount),
                status=s.status,
                settlement_date=s.settlement_date.isoformat() if s.settlement_date else None,
                created_at=s.created_at.isoformat(),
            )
        )
    return responses


@router.get(
    "/merchants/{merchant_id}",
    response_model=list[SettlementResponse],
    status_code=status.HTTP_200_OK,
)
async def get_merchant_settlements(
    merchant_id: str,
    limit: int = Query(default=20, le=100),
    _: UserClaims = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session),
) -> list[SettlementResponse]:
    """Settlement history for a specific restaurant."""
    try:
        merchant_uuid = uuid.UUID(merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant_id")

    result = await session.execute(
        select(MerchantSettlement)
        .where(MerchantSettlement.merchant_id == merchant_uuid)
        .order_by(desc(MerchantSettlement.created_at))
        .limit(limit)
    )
    settlements = result.scalars().all()
    return [
        SettlementResponse(
            id=str(s.id),
            merchant_id=str(s.merchant_id),
            merchant_name=None,
            settlement_id=s.settlement_id,
            gross_amount=float(s.gross_amount),
            commission_deducted=float(s.commission_deducted),
            net_amount=float(s.net_amount),
            status=s.status,
            settlement_date=s.settlement_date.isoformat() if s.settlement_date else None,
            created_at=s.created_at.isoformat(),
        )
        for s in settlements
    ]
