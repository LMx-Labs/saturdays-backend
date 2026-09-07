import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.authorization import require_branch_access
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.merchant.repository import MerchantRepository
from app.reports.repository import ReportsRepository
from app.reports.schemas import (
    BranchPerformance,
    CommissionSummary,
    PaymentRefundSummary,
    PlatformOperationalSummary,
    SalesSummary,
)
from app.reports.service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])


def get_reports_service(session: AsyncSession = Depends(get_db_session)) -> ReportsService:
    return ReportsService(ReportsRepository(session))


@router.get("/merchant/sales", response_model=SalesSummary)
async def merchant_sales(
    branch_id: uuid.UUID,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    service: ReportsService = Depends(get_reports_service),
) -> SalesSummary:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    summary, _, _ = await service.sales(branch_id, date_from, date_to)
    return summary


@router.get("/branches/{branch_id}/performance", response_model=BranchPerformance)
async def branch_performance(
    branch_id: uuid.UUID,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    service: ReportsService = Depends(get_reports_service),
) -> BranchPerformance:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await service.branch_performance(branch_id, date_from, date_to)


@router.get("/payments-refunds", response_model=PaymentRefundSummary)
async def payment_refunds(
    branch_id: uuid.UUID,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    service: ReportsService = Depends(get_reports_service),
) -> PaymentRefundSummary:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await service.payments(branch_id, date_from, date_to)


@router.get("/commissions", response_model=CommissionSummary)
async def commissions(
    merchant_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: UserClaims = Depends(require_role(["MerchantOwner", "PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
    service: ReportsService = Depends(get_reports_service),
) -> CommissionSummary:
    if current_user.role == "PlatformAdmin":
        if merchant_id is None:
            raise EntityNotFoundError("merchant_id is required.", "MERCHANT_ID_REQUIRED")
        scoped_merchant_id = merchant_id
    else:
        merchant = await MerchantRepository(session).get_by_owner_user_id(
            uuid.UUID(current_user.sub)
        )
        if not merchant:
            raise EntityNotFoundError("Merchant not found.", "MERCHANT_NOT_FOUND")
        scoped_merchant_id = merchant.id
    return await service.commissions(scoped_merchant_id, date_from, date_to)


@router.get("/platform/operations", response_model=PlatformOperationalSummary)
async def platform_operations(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    _current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    service: ReportsService = Depends(get_reports_service),
) -> PlatformOperationalSummary:
    return await service.platform(date_from, date_to)
