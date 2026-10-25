import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_branch_access
from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.branch.models import Branch
from app.branch.repository import BranchRepository, BranchRepositoryInterface
from app.branch.schemas import (
    BranchCreateRequest,
    BranchResponse,
    BranchStatusUpdateRequest,
    BranchUpdateRequest,
)
from app.branch.service import BranchService, BranchServiceInterface
from app.brand.repository import BrandRepository, BrandRepositoryInterface
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.kitchen.models import Kitchen
from app.menu.models import Menu
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface

router = APIRouter(prefix="/branches", tags=["Branch"])


@router.post("/{branch_id}/workspace/initialize", status_code=200)
async def initialize_branch_workspace(
    branch_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Repair an existing incomplete branch without creating duplicate units or stock."""
    await require_branch_access(session, current_user, branch_id)
    branch = await session.scalar(
        select(Branch)
        .where(Branch.id == branch_id, Branch.deleted_at.is_(None))
        .with_for_update()
    )
    if branch is None:
        raise EntityNotFoundError("Branch not found.", "BRANCH_NOT_FOUND")
    menu = await session.scalar(
        select(Menu)
        .where(Menu.branch_id == branch_id, Menu.deleted_at.is_(None))
        .limit(1)
    )
    if menu is None:
        menu = Menu(branch_id=branch_id, name="Main Menu", is_active=True)
        session.add(menu)
    kitchen = await session.scalar(
        select(Kitchen)
        .where(Kitchen.branch_id == branch_id, Kitchen.deleted_at.is_(None))
        .limit(1)
    )
    if kitchen is None:
        kitchen = Kitchen(branch_id=branch_id, name="Main Kitchen", is_active=True)
        session.add(kitchen)
    await session.commit()
    return {
        "branch_id": str(branch_id),
        "menu_id": str(menu.id),
        "kitchen_id": str(kitchen.id),
    }


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


def get_branch_service(
    session: AsyncSession = Depends(get_db_session),
    branch_repo: BranchRepositoryInterface = Depends(get_branch_repository),
    brand_repo: BrandRepositoryInterface = Depends(get_brand_repository),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> BranchServiceInterface:
    return BranchService(
        session=session,
        branch_repo=branch_repo,
        brand_repo=brand_repo,
        merchant_repo=merchant_repo,
    )


@router.get(
    "",
    response_model=list[BranchResponse],
    status_code=status.HTTP_200_OK,
    summary="List active physical branches",
    description="Public endpoint returning active branch locations for customer discovery.",
)
async def list_branches(
    brand_id: str | None = Query(None, description="Optional brand ID filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> list[BranchResponse]:
    return await branch_service.list_branches(brand_id=brand_id, skip=skip, limit=limit)


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create physical branch location",
    description="Creates a physical branch store location under a valid brand identity.",
)
async def create_branch(
    req: BranchCreateRequest,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> BranchResponse:
    is_admin = current_user.role == "PlatformAdmin"
    return await branch_service.create_branch(
        user_id=current_user.sub, is_admin=is_admin, req=req
    )


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get branch by ID",
    description="Public endpoint returning physical store branch profile details by UUID.",
)
async def get_branch_by_id(
    branch_id: str,
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> BranchResponse:
    return await branch_service.get_branch_by_id(branch_id)


@router.patch(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Update branch details",
    description="Updates store profile, location coordinates, or operating hours.",
)
async def update_branch(
    branch_id: str,
    req: BranchUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> BranchResponse:
    await require_branch_access(session, current_user, uuid.UUID(branch_id))
    is_admin = current_user.role in {"PlatformAdmin", "BranchManager"}
    return await branch_service.update_branch(
        branch_id=branch_id, user_id=current_user.sub, is_admin=is_admin, req=req
    )


@router.patch(
    "/{branch_id}/status",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle branch active status",
    description="Toggles store online/offline active state.",
)
async def update_branch_status(
    branch_id: str,
    req: BranchStatusUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> BranchResponse:
    await require_branch_access(session, current_user, uuid.UUID(branch_id))
    is_admin = current_user.role in {"PlatformAdmin", "BranchManager"}
    return await branch_service.update_branch_status(
        branch_id=branch_id, user_id=current_user.sub, is_admin=is_admin, req=req
    )


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete branch",
    description="Soft deletes a physical store branch profile.",
)
async def delete_branch(
    branch_id: str,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    branch_service: BranchServiceInterface = Depends(get_branch_service),
) -> None:
    is_admin = current_user.role == "PlatformAdmin"
    await branch_service.delete_branch(
        branch_id=branch_id, user_id=current_user.sub, is_admin=is_admin
    )
