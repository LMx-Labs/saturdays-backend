from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.brand.repository import BrandRepository, BrandRepositoryInterface
from app.brand.schemas import BrandCreateRequest, BrandResponse, BrandUpdateRequest
from app.brand.service import BrandService, BrandServiceInterface
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface

router = APIRouter(prefix="/brands", tags=["Brand"])


def get_brand_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BrandRepositoryInterface:
    return BrandRepository(session=session)


def get_merchant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantRepositoryInterface:
    return MerchantRepository(session=session)


def get_brand_service(
    session: AsyncSession = Depends(get_db_session),
    brand_repo: BrandRepositoryInterface = Depends(get_brand_repository),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> BrandServiceInterface:
    return BrandService(
        session=session,
        brand_repo=brand_repo,
        merchant_repo=merchant_repo,
    )


@router.get(
    "",
    response_model=list[BrandResponse],
    status_code=status.HTTP_200_OK,
    summary="List active brands catalog",
    description="Public endpoint returning active restaurant brands.",
)
async def list_brands(
    merchant_id: str | None = Query(None, description="Optional merchant ID filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    brand_service: BrandServiceInterface = Depends(get_brand_service),
) -> list[BrandResponse]:
    return await brand_service.list_brands(
        merchant_id=merchant_id, skip=skip, limit=limit
    )


@router.post(
    "",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create brand profile",
    description="Creates a new brand identity under a registered merchant entity.",
)
async def create_brand(
    req: BrandCreateRequest,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    brand_service: BrandServiceInterface = Depends(get_brand_service),
) -> BrandResponse:
    is_admin = current_user.role == "PlatformAdmin"
    return await brand_service.create_brand(
        user_id=current_user.sub, is_admin=is_admin, req=req
    )


@router.get(
    "/{brand_id}",
    response_model=BrandResponse,
    status_code=status.HTTP_200_OK,
    summary="Get brand by ID",
    description="Public endpoint returning brand details by UUID.",
)
async def get_brand_by_id(
    brand_id: str,
    brand_service: BrandServiceInterface = Depends(get_brand_service),
) -> BrandResponse:
    return await brand_service.get_brand_by_id(brand_id)


@router.patch(
    "/{brand_id}",
    response_model=BrandResponse,
    status_code=status.HTTP_200_OK,
    summary="Update brand details",
    description="Updates brand marketing metadata, logos, or cuisine categories.",
)
async def update_brand(
    brand_id: str,
    req: BrandUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    brand_service: BrandServiceInterface = Depends(get_brand_service),
) -> BrandResponse:
    is_admin = current_user.role == "PlatformAdmin"
    return await brand_service.update_brand(
        brand_id=brand_id, user_id=current_user.sub, is_admin=is_admin, req=req
    )


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete brand",
    description="Soft deletes a brand identity.",
)
async def delete_brand(
    brand_id: str,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "PlatformAdmin"])
    ),
    brand_service: BrandServiceInterface = Depends(get_brand_service),
) -> None:
    is_admin = current_user.role == "PlatformAdmin"
    await brand_service.delete_brand(
        brand_id=brand_id, user_id=current_user.sub, is_admin=is_admin
    )
