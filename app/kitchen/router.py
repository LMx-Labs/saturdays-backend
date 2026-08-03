from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.branch.repository import BranchRepository, BranchRepositoryInterface
from app.brand.repository import BrandRepository, BrandRepositoryInterface
from app.core.database import get_db_session
from app.kitchen.repository import KitchenRepository, KitchenRepositoryInterface
from app.kitchen.schemas import (
    KitchenCreateRequest,
    KitchenResponse,
    KitchenUpdateRequest,
)
from app.kitchen.service import KitchenService, KitchenServiceInterface
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface

router = APIRouter(prefix="", tags=["Kitchen"])


def get_kitchen_repository(
    session: AsyncSession = Depends(get_db_session),
) -> KitchenRepositoryInterface:
    return KitchenRepository(session=session)


def get_branch_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BranchRepositoryInterface:
    return BranchRepository(session=session)


def get_brand_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BrandRepositoryInterface:
    return BrandRepository(session=session)


def get_merchant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantRepositoryInterface:
    return MerchantRepository(session=session)


def get_kitchen_service(
    session: AsyncSession = Depends(get_db_session),
    kitchen_repo: KitchenRepositoryInterface = Depends(get_kitchen_repository),
    branch_repo: BranchRepositoryInterface = Depends(get_branch_repository),
    brand_repo: BrandRepositoryInterface = Depends(get_brand_repository),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> KitchenServiceInterface:
    return KitchenService(
        session=session,
        kitchen_repo=kitchen_repo,
        branch_repo=branch_repo,
        brand_repo=brand_repo,
        merchant_repo=merchant_repo,
    )


@router.get(
    "/branches/{branch_id}/kitchens",
    response_model=list[KitchenResponse],
    status_code=status.HTTP_200_OK,
    summary="List branch kitchen units",
    description="Returns kitchen preparation stations/units for a branch.",
)
async def list_branch_kitchens(
    branch_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: UserClaims = Depends(
        require_role(
            ["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"]
        )
    ),
    kitchen_service: KitchenServiceInterface = Depends(get_kitchen_service),
) -> list[KitchenResponse]:
    return await kitchen_service.list_branch_kitchens(
        branch_id=branch_id,
        user_id=current_user.sub,
        role=current_user.role,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/kitchens",
    response_model=KitchenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create kitchen unit",
    description="Creates a operational food preparation unit under a physical branch.",
)
async def create_kitchen(
    req: KitchenCreateRequest,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    kitchen_service: KitchenServiceInterface = Depends(get_kitchen_service),
) -> KitchenResponse:
    return await kitchen_service.create_kitchen(
        user_id=current_user.sub, role=current_user.role, req=req
    )


@router.get(
    "/kitchens/{kitchen_id}",
    response_model=KitchenResponse,
    status_code=status.HTTP_200_OK,
    summary="Get kitchen by ID",
    description="Returns kitchen profile details by UUID.",
)
async def get_kitchen_by_id(
    kitchen_id: str,
    current_user: UserClaims = Depends(
        require_role(
            ["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"]
        )
    ),
    kitchen_service: KitchenServiceInterface = Depends(get_kitchen_service),
) -> KitchenResponse:
    return await kitchen_service.get_kitchen_by_id(
        kitchen_id=kitchen_id, user_id=current_user.sub, role=current_user.role
    )


@router.patch(
    "/kitchens/{kitchen_id}",
    response_model=KitchenResponse,
    status_code=status.HTTP_200_OK,
    summary="Update kitchen details",
    description="Updates kitchen unit name or active status.",
)
async def update_kitchen(
    kitchen_id: str,
    req: KitchenUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    kitchen_service: KitchenServiceInterface = Depends(get_kitchen_service),
) -> KitchenResponse:
    return await kitchen_service.update_kitchen(
        kitchen_id=kitchen_id, user_id=current_user.sub, role=current_user.role, req=req
    )


@router.delete(
    "/kitchens/{kitchen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete kitchen unit",
    description="Soft deletes a kitchen unit.",
)
async def delete_kitchen(
    kitchen_id: str,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    kitchen_service: KitchenServiceInterface = Depends(get_kitchen_service),
) -> None:
    await kitchen_service.delete_kitchen(
        kitchen_id=kitchen_id, user_id=current_user.sub, role=current_user.role
    )
