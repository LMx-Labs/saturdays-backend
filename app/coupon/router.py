import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.authorization import get_optional_current_user, require_branch_access
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, ForbiddenError
from app.coupon.models import Coupon, CouponRedemption
from app.coupon.repository import CouponRepository, CouponRepositoryInterface
from app.coupon.schemas import (
    CouponCreate,
    CouponRedemptionResponse,
    CouponResponse,
    CouponUpdate,
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
    return CouponService(session=session, coupon_repo=coupon_repo, customer_repo=customer_repo)


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
    return await coupon_service.validate_coupon(user_id=uuid.UUID(current_user.sub), req=req)


@router.post(
    "",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new promotional coupon",
)
async def create_coupon(
    req: CouponCreate,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CouponResponse:
    if current_user.role != "PlatformAdmin":
        if req.branch_id is None:
            raise ForbiddenError("Only platform admins can create global coupons.")
        await require_branch_access(session, current_user.sub, current_user.role, req.branch_id)
    return await coupon_service.create_coupon(req=req)


@router.get(
    "",
    response_model=list[CouponResponse],
    status_code=status.HTTP_200_OK,
    summary="List active promotional coupons",
)
async def list_coupons(
    branch_id: uuid.UUID | None = Query(None),
    active: bool | None = Query(None),
    current_user: UserClaims | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db_session),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> list[CouponResponse]:
    if current_user is None or current_user.role == "Customer":
        return await coupon_service.list_available_coupons(branch_id=branch_id)
    if current_user.role != "PlatformAdmin":
        if branch_id is None:
            raise ForbiddenError("branch_id is required.", "BRANCH_ID_REQUIRED")
        await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    stmt = select(Coupon).where(Coupon.deleted_at.is_(None))
    if branch_id:
        stmt = stmt.where(Coupon.branch_id == branch_id)
    if active is not None:
        stmt = stmt.where(Coupon.is_active == active)
    coupons = (await session.execute(stmt.order_by(Coupon.created_at.desc()))).scalars()
    return [CouponResponse.model_validate(coupon) for coupon in coupons]


@router.get(
    "/{coupon_id}",
    response_model=CouponResponse,
    status_code=status.HTTP_200_OK,
    summary="Get coupon details by ID",
)
async def get_coupon(
    coupon_id: uuid.UUID,
    current_user: UserClaims | None = Depends(get_optional_current_user),
    session: AsyncSession = Depends(get_db_session),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CouponResponse:
    coupon = await coupon_service.get_coupon_by_id(coupon_id=coupon_id)
    if (current_user is None or current_user.role == "Customer") and not coupon.is_active:
        raise EntityNotFoundError("Coupon not found.", "COUPON_NOT_FOUND")
    if current_user is not None and current_user.role not in {"Customer", "PlatformAdmin"}:
        if coupon.branch_id is None:
            raise ForbiddenError("Coupon access denied.", "COUPON_ACCESS_FORBIDDEN")
        await require_branch_access(session, current_user.sub, current_user.role, coupon.branch_id)
    return coupon


@router.patch("/{coupon_id}", response_model=CouponResponse)
async def update_coupon(
    coupon_id: uuid.UUID,
    req: CouponUpdate,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CouponResponse:
    coupon = await session.get(Coupon, coupon_id)
    if not coupon or coupon.deleted_at is not None:
        raise EntityNotFoundError("Coupon not found.", "COUPON_NOT_FOUND")
    if current_user.role != "PlatformAdmin":
        if coupon.branch_id is None:
            raise ForbiddenError("Coupon access denied.", "COUPON_ACCESS_FORBIDDEN")
        await require_branch_access(session, current_user.sub, current_user.role, coupon.branch_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    if coupon.valid_until <= coupon.valid_from:
        from app.core.exceptions import UnprocessableEntityError

        raise UnprocessableEntityError("valid_until must be after valid_from.")
    await session.commit()
    await session.refresh(coupon)
    return CouponResponse.model_validate(coupon)


@router.post("/{coupon_id}/activate", response_model=CouponResponse)
async def activate_coupon(
    coupon_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CouponResponse:
    return await _set_coupon_active(coupon_id, True, current_user, session)


@router.post("/{coupon_id}/deactivate", response_model=CouponResponse)
async def deactivate_coupon(
    coupon_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> CouponResponse:
    return await _set_coupon_active(coupon_id, False, current_user, session)


async def _set_coupon_active(
    coupon_id: uuid.UUID,
    active: bool,
    current_user: UserClaims,
    session: AsyncSession,
) -> CouponResponse:
    coupon = await session.get(Coupon, coupon_id)
    if not coupon or coupon.deleted_at is not None:
        raise EntityNotFoundError("Coupon not found.", "COUPON_NOT_FOUND")
    if current_user.role != "PlatformAdmin":
        if coupon.branch_id is None:
            raise ForbiddenError("Coupon access denied.", "COUPON_ACCESS_FORBIDDEN")
        await require_branch_access(session, current_user.sub, current_user.role, coupon.branch_id)
    coupon.is_active = active
    await session.commit()
    await session.refresh(coupon)
    return CouponResponse.model_validate(coupon)


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    coupon = await session.get(Coupon, coupon_id)
    if not coupon or coupon.deleted_at is not None:
        raise EntityNotFoundError("Coupon not found.", "COUPON_NOT_FOUND")
    if current_user.role != "PlatformAdmin":
        if coupon.branch_id is None:
            raise ForbiddenError("Coupon access denied.", "COUPON_ACCESS_FORBIDDEN")
        await require_branch_access(session, current_user.sub, current_user.role, coupon.branch_id)
    coupon.soft_delete()
    await session.commit()


@router.get("/{coupon_id}/redemptions", response_model=list[CouponRedemptionResponse])
async def list_coupon_redemptions(
    coupon_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["MerchantOwner", "BranchManager", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[CouponRedemptionResponse]:
    coupon = await session.get(Coupon, coupon_id)
    if not coupon or coupon.deleted_at is not None:
        raise EntityNotFoundError("Coupon not found.", "COUPON_NOT_FOUND")
    if current_user.role != "PlatformAdmin":
        if coupon.branch_id is None:
            raise ForbiddenError("Coupon access denied.", "COUPON_ACCESS_FORBIDDEN")
        await require_branch_access(session, current_user.sub, current_user.role, coupon.branch_id)
    rows = (
        await session.execute(
            select(CouponRedemption)
            .where(CouponRedemption.coupon_id == coupon_id)
            .order_by(CouponRedemption.created_at.desc())
        )
    ).scalars()
    return [CouponRedemptionResponse.model_validate(row) for row in rows]
