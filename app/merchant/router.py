import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.branch.models import Branch
from app.branch.schemas import BranchResponse
from app.brand.models import Brand
from app.merchant.models import Merchant, MerchantStaffMembership, StaffBranchAssignment
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface
from app.merchant.schemas import (
    MerchantOnboardRequest,
    MerchantResponse,
    MerchantStatusUpdateRequest,
    MerchantUpdateRequest,
)
from app.merchant.service import MerchantService, MerchantServiceInterface

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


@router.get("/me/branches", response_model=list[BranchResponse])
async def list_my_merchant_branches(
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "KitchenStaff"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[BranchResponse]:
    user_id = uuid.UUID(current_user.sub)
    if current_user.role == "MerchantOwner":
        stmt = (
            select(Branch)
            .join(Brand, Brand.id == Branch.brand_id)
            .join(Merchant, Merchant.id == Brand.merchant_id)
            .where(Merchant.owner_user_id == user_id, Branch.deleted_at.is_(None))
        )
    else:
        stmt = (
            select(Branch)
            .join(StaffBranchAssignment, StaffBranchAssignment.branch_id == Branch.id)
            .join(
                MerchantStaffMembership,
                MerchantStaffMembership.id == StaffBranchAssignment.membership_id,
            )
            .where(
                MerchantStaffMembership.user_id == user_id,
                MerchantStaffMembership.is_active.is_(True),
                Branch.deleted_at.is_(None),
            )
        )
    branches = (await session.execute(stmt.order_by(Branch.created_at.desc()))).scalars()
    return [BranchResponse.model_validate(branch) for branch in branches]


@router.get(
    "/me",
    response_model=MerchantResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user's merchant profile",
    description="Returns authenticated merchant owner's legal entity profile.",
)
async def get_my_merchant_profile(
    current_user: UserClaims = Depends(require_role(["MerchantOwner", "PlatformAdmin"])),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.get_current_merchant_profile(current_user.sub)


@router.post(
    "/onboard",
    response_model=MerchantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new merchant entity",
    description="Registers legal business entity, tax details (GSTIN/FSSAI), and bank details for current user.",
)
async def onboard_merchant(
    req: MerchantOnboardRequest,
    current_user: UserClaims = Depends(require_role(["MerchantOwner", "PlatformAdmin"])),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    return await merchant_service.onboard_merchant(owner_user_id=current_user.sub, req=req)


@router.post("/me/submit", response_model=MerchantResponse)
async def submit_my_merchant_for_verification(
    current_user: UserClaims = Depends(require_role(["MerchantOwner"])),
    merchant_service: MerchantServiceInterface = Depends(get_merchant_service),
) -> MerchantResponse:
    merchant = await merchant_service.get_current_merchant_profile(current_user.sub)
    return await merchant_service.update_merchant_status(
        merchant.id, MerchantStatusUpdateRequest(status="PENDING_VERIFICATION")
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
    merchant = await merchant_service.get_merchant_by_id(merchant_id)
    if current_user.role != "PlatformAdmin" and merchant.owner_user_id != current_user.sub:
        if merchant.bank_account_number:
            merchant.bank_account_number = (
                "*" * max(0, len(merchant.bank_account_number) - 4)
                + merchant.bank_account_number[-4:]
            )
        merchant.bank_ifsc_code = None
    return merchant


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
    current_user: UserClaims = Depends(require_role(["MerchantOwner", "PlatformAdmin"])),
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
    return await merchant_service.update_merchant_status(merchant_id=merchant_id, req=req)
