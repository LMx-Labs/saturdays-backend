"""Admin settlement cycle management + transaction history.

Registered at /api/v1/admin/settlements
"""
import uuid
from datetime import UTC, date, datetime
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


def _parse_settlement_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        clean = val.split("T")[0].strip()
        return date.fromisoformat(clean)
    except Exception:
        return None


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


class SettlementCreateRequest(BaseModel):
    merchant_id: str
    gross_amount: float
    commission_deducted: float = 0.0
    net_amount: float | None = None
    status: Literal["PENDING", "IN_TRANSIT", "SETTLED", "FAILED"] = "PENDING"
    settlement_id: str | None = None
    settlement_date: str | None = None


class SettlementUpdateRequest(BaseModel):
    status: Literal["PENDING", "IN_TRANSIT", "SETTLED", "FAILED"] | None = None
    settlement_id: str | None = None
    settlement_date: str | None = None
    gross_amount: float | None = None
    commission_deducted: float | None = None
    net_amount: float | None = None


@router.patch(
    "/merchants/{merchant_id}/cycle",
    response_model=SettlementCycleResponse,
    status_code=status.HTTP_200_OK,
)
async def update_settlement_cycle(
    merchant_id: str,
    req: SettlementCycleRequest,
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
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
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
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
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
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


@router.get(
    "/my",
    response_model=list[SettlementResponse],
    status_code=status.HTTP_200_OK,
    summary="Get settlements for currently logged-in restaurant merchant",
)
async def get_current_user_settlements(
    limit: int = Query(default=50, le=200),
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "KitchenStaff", "PlatformAdmin", "Admin", "admin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[SettlementResponse]:
    """Retrieve settlement records for the caller's restaurant merchant."""
    merchant_repo = MerchantRepository(session=session)
    merchant_id: uuid.UUID | None = None

    try:
        user_uuid = uuid.UUID(current_user.sub)
    except (ValueError, TypeError):
        user_uuid = None

    if user_uuid:
        merchant = await merchant_repo.get_by_owner_user_id(user_uuid)
        if merchant:
            merchant_id = merchant.id

    if not merchant_id and getattr(current_user, "branch_id", None):
        try:
            b_uuid = uuid.UUID(str(current_user.branch_id))
            from app.branch.models import Branch
            from app.brand.models import Brand

            b_res = await session.execute(
                select(Brand.merchant_id)
                .join(Branch, Branch.brand_id == Brand.id)
                .where(Branch.id == b_uuid)
            )
            merchant_id = b_res.scalar_one_or_none()
        except Exception as e:
            logger.warning("Failed resolving merchant from branch_id", error=str(e))

    # Fallback: if caller is PlatformAdmin and no specific merchant, pick first merchant or return empty
    if not merchant_id:
        if current_user.role in ["PlatformAdmin", "Admin", "admin"]:
            first_m = await session.execute(select(MerchantSettlement.merchant_id).limit(1))
            merchant_id = first_m.scalar_one_or_none()

    if not merchant_id:
        return []

    result = await session.execute(
        select(MerchantSettlement)
        .where(MerchantSettlement.merchant_id == merchant_id)
        .order_by(desc(MerchantSettlement.created_at))
        .limit(limit)
    )
    settlements = result.scalars().all()
    merchant = await merchant_repo.get_by_id(merchant_id)
    merchant_name = getattr(merchant, "business_name", None) if merchant else None

    return [
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
        for s in settlements
    ]


@router.post(
    "",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new merchant settlement record",
)
async def create_settlement(
    req: SettlementCreateRequest,
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
    session: AsyncSession = Depends(get_db_session),
) -> SettlementResponse:
    """Admin manually issues or records a settlement for a merchant."""
    try:
        merchant_uuid = uuid.UUID(req.merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant_id")

    net = (
        req.net_amount
        if req.net_amount is not None
        else max(0.0, req.gross_amount - req.commission_deducted)
    )
    s_date = _parse_settlement_date(req.settlement_date) or date.today()

    settlement = MerchantSettlement(
        merchant_id=merchant_uuid,
        settlement_id=req.settlement_id,
        gross_amount=req.gross_amount,
        commission_deducted=req.commission_deducted,
        net_amount=net,
        status=req.status.upper(),
        settlement_date=s_date,
    )
    session.add(settlement)
    await session.commit()
    await session.refresh(settlement)

    merchant_repo = MerchantRepository(session=session)
    merchant = await merchant_repo.get_by_id(merchant_uuid)
    merchant_name = getattr(merchant, "business_name", None) if merchant else None

    logger.info(
        "Settlement created",
        settlement_id=str(settlement.id),
        merchant_id=str(settlement.merchant_id),
        net_amount=float(settlement.net_amount),
        status=settlement.status,
    )

    return SettlementResponse(
        id=str(settlement.id),
        merchant_id=str(settlement.merchant_id),
        merchant_name=merchant_name,
        settlement_id=settlement.settlement_id,
        gross_amount=float(settlement.gross_amount),
        commission_deducted=float(settlement.commission_deducted),
        net_amount=float(settlement.net_amount),
        status=settlement.status,
        settlement_date=settlement.settlement_date.isoformat() if settlement.settlement_date else None,
        created_at=settlement.created_at.isoformat(),
    )


@router.patch(
    "/{settlement_id}",
    response_model=SettlementResponse,
    status_code=status.HTTP_200_OK,
    summary="Update settlement status, UTR / reference ID, or date",
)
async def update_settlement(
    settlement_id: str,
    req: SettlementUpdateRequest,
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
    session: AsyncSession = Depends(get_db_session),
) -> SettlementResponse:
    """Admin updates status (e.g. SETTLED, IN_TRANSIT), bank UTR, or payout date."""
    try:
        s_uuid = uuid.UUID(settlement_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid settlement_id")

    result = await session.execute(
        select(MerchantSettlement).where(MerchantSettlement.id == s_uuid)
    )
    settlement = result.scalar_one_or_none()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if req.status is not None:
        settlement.status = req.status.upper()
    if req.settlement_id is not None:
        settlement.settlement_id = req.settlement_id
    if req.settlement_date is not None:
        settlement.settlement_date = _parse_settlement_date(req.settlement_date)
    if req.gross_amount is not None:
        settlement.gross_amount = req.gross_amount
    if req.commission_deducted is not None:
        settlement.commission_deducted = req.commission_deducted
    if req.net_amount is not None:
        settlement.net_amount = req.net_amount
    elif req.gross_amount is not None or req.commission_deducted is not None:
        settlement.net_amount = max(
            0.0, float(settlement.gross_amount) - float(settlement.commission_deducted)
        )

    await session.commit()
    await session.refresh(settlement)

    merchant_repo = MerchantRepository(session=session)
    merchant = await merchant_repo.get_by_id(settlement.merchant_id)
    merchant_name = getattr(merchant, "business_name", None) if merchant else None

    logger.info(
        "Settlement updated",
        settlement_id=str(settlement.id),
        status=settlement.status,
        utr=settlement.settlement_id,
    )

    return SettlementResponse(
        id=str(settlement.id),
        merchant_id=str(settlement.merchant_id),
        merchant_name=merchant_name,
        settlement_id=settlement.settlement_id,
        gross_amount=float(settlement.gross_amount),
        commission_deducted=float(settlement.commission_deducted),
        net_amount=float(settlement.net_amount),
        status=settlement.status,
        settlement_date=settlement.settlement_date.isoformat() if settlement.settlement_date else None,
        created_at=settlement.created_at.isoformat(),
    )
