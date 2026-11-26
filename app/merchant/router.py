from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface
from app.merchant.schemas import (
    MerchantOnboardRequest,
    MerchantResponse,
    MerchantStatusUpdateRequest,
    MerchantUpdateRequest,
)
from app.merchant.service import MerchantService, MerchantServiceInterface
from app.subscription.models import MerchantSettlement
from app.subscription.settlement_router import SettlementResponse

router = APIRouter(prefix="/merchants", tags=["Merchant"])


def get_merchant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantRepositoryInterface:
    return MerchantRepository(session=session)


def get_merchant_service(
    session: AsyncSession = Depends(get_db_session),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> MerchantServiceInterface:
    return MerchantService(session=session, merchant_repo=merchant_repo)


@router.get(
    "/me",
    response_model=MerchantResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user's merchant profile",
    description="Returns authenticated merchant owner's legal entity profile.",
)
async def get_my_merchant_profile(
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.get_current_merchant_profile(current_user.sub)


@router.get(
    "/me/settlements",
    response_model=list[SettlementResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current merchant's settlements and payouts",
    description="Returns settlement payout history, status, and bank UTR reference numbers.",
)
async def get_my_merchant_settlements(
    limit: int = Query(default=50, le=200),
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "KitchenStaff", "PlatformAdmin", "Admin", "admin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> list[SettlementResponse]:
    import uuid
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
        except Exception:
            pass

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
    "/onboard",
    response_model=MerchantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new merchant entity",
    description="Registers legal business entity, tax details (GSTIN/FSSAI), and bank details for current user.",
)
async def onboard_merchant(
    req: MerchantOnboardRequest,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.onboard_merchant(
        owner_user_id=current_user.sub, req=req
    )


@router.get(
    "/{merchant_id}",
    response_model=MerchantResponse,
    status_code=status.HTTP_200_OK,
    summary="Get merchant by ID",
    description="Fetches merchant profile by UUID.",
)
async def get_merchant_by_id(
    merchant_id: str,
    current_user: UserClaims = Depends(get_current_user),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.get_merchant_by_id(merchant_id)


@router.patch(
    "/{merchant_id}",
    response_model=MerchantResponse,
    status_code=status.HTTP_200_OK,
    summary="Update merchant profile",
    description="Updates business name, legal entity name, FSSAI, GSTIN, or bank details.",
)
async def update_merchant(
    merchant_id: str,
    req: MerchantUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    is_admin = current_user.role == "PlatformAdmin"
    return await merchant_service.update_merchant(
        merchant_id=merchant_id,
        owner_user_id=current_user.sub,
        req=req,
        is_admin=is_admin,
    )


@router.patch(
    "/{merchant_id}/status",
    response_model=MerchantResponse,
    status_code=status.HTTP_200_OK,
    summary="Update merchant status (Admin)",
    description="Transitions merchant lifecycle status (e.g. DRAFT -> PENDING_VERIFICATION -> APPROVED).",
)
async def update_merchant_status(
    merchant_id: str,
    req: MerchantStatusUpdateRequest,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.update_merchant_status(
        merchant_id=merchant_id, req=req
    )
