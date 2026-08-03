import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.coupon.repository import CouponRepository, CouponRepositoryInterface
from app.coupon.schemas import (
    CouponCreate,
    CouponResponse,
    CouponValidateRequest,
    CouponValidateResponse,
)
from app.coupon.service import CouponService, CouponServiceInterface
from app.customer.repository import CustomerRepository, CustomerRepositoryInterface

router = APIRouter(prefix="/coupons", tags=["Coupon"])


def get_coupon_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CouponRepositoryInterface:
    return CouponRepository(session=session)


def get_customer_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CustomerRepositoryInterface:
    return CustomerRepository(session=session)


def get_coupon_service(
    session: AsyncSession = Depends(get_db_session),
    coupon_repo: CouponRepositoryInterface = Depends(get_coupon_repository),
    customer_repo: CustomerRepositoryInterface = Depends(get_customer_repository),
) -> CouponServiceInterface:
    return CouponService(
        session=session, coupon_repo=coupon_repo, customer_repo=customer_repo
    )


@router.post(
    "/validate",
    response_model=CouponValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate promotional coupon and calculate discount",
)
async def validate_coupon(
    req: CouponValidateRequest,
    current_user: UserClaims = Depends(get_current_user),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CouponValidateResponse:
    return await coupon_service.validate_coupon(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.post(
    "",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new promotional coupon",
)
async def create_coupon(
    req: CouponCreate,
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CouponResponse:
    return await coupon_service.create_coupon(req=req)


@router.get(
    "",
    response_model=list[CouponResponse],
    status_code=status.HTTP_200_OK,
    summary="List active promotional coupons",
)
async def list_coupons(
    branch_id: uuid.UUID | None = Query(None),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> list[CouponResponse]:
    return await coupon_service.list_available_coupons(branch_id=branch_id)


@router.get(
    "/{coupon_id}",
    response_model=CouponResponse,
    status_code=status.HTTP_200_OK,
    summary="Get coupon details by ID",
)
async def get_coupon(
    coupon_id: uuid.UUID,
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CouponResponse:
    return await coupon_service.get_coupon_by_id(coupon_id=coupon_id)
