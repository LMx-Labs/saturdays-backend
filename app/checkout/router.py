from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.admin.models import FeatureFlag
from app.checkout.repository import CheckoutRepository, CheckoutRepositoryInterface
from app.checkout.schemas import CheckoutValidateRequest, CheckoutValidationResponse
from app.checkout.service import CheckoutService, CheckoutServiceInterface
from app.core.database import get_db_session
from app.coupon.repository import CouponRepository, CouponRepositoryInterface
from app.coupon.service import CouponService, CouponServiceInterface
from app.customer.repository import CustomerRepository

router = APIRouter(prefix="/checkout", tags=["Checkout"])


async def require_checkout_available(
    session: AsyncSession = Depends(get_db_session),
) -> None:
    flag = await session.get(FeatureFlag, "EMERGENCY_MAINTENANCE_MODE")
    if flag and flag.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkout is temporarily unavailable.",
        )


def get_checkout_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutRepositoryInterface:
    return CheckoutRepository(session=session)


def get_coupon_service(
    session: AsyncSession = Depends(get_db_session),
) -> CouponServiceInterface:
    coupon_repo: CouponRepositoryInterface = CouponRepository(session=session)
    customer_repo = CustomerRepository(session=session)
    return CouponService(session=session, coupon_repo=coupon_repo, customer_repo=customer_repo)


def get_checkout_service(
    session: AsyncSession = Depends(get_db_session),
    checkout_repo: CheckoutRepositoryInterface = Depends(get_checkout_repository),
    coupon_service: CouponServiceInterface = Depends(get_coupon_service),
) -> CheckoutServiceInterface:
    return CheckoutService(
        session=session,
        checkout_repo=checkout_repo,
        coupon_service=coupon_service,
    )


@router.post(
    "/validate",
    response_model=CheckoutValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate checkout pre-order session",
    description="Validates customer, branch availability, kitchen, stock, cart items, coupon discounts, and calculates taxes and delivery fee.",
)
async def validate_checkout(
    req: CheckoutValidateRequest,
    current_user: UserClaims = Depends(require_role(["Customer"])),
    _available: None = Depends(require_checkout_available),
    checkout_service: CheckoutServiceInterface = Depends(get_checkout_service),
) -> CheckoutValidationResponse:
    return await checkout_service.validate_checkout(user_id=current_user.sub, req=req)


@router.post(
    "/summary",
    response_model=CheckoutValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get checkout financial summary",
    description="Returns full pre-order financial breakup including subtotal, GST tax, delivery fee, and final payable amount.",
)
async def get_checkout_summary(
    req: CheckoutValidateRequest,
    current_user: UserClaims = Depends(require_role(["Customer"])),
    _available: None = Depends(require_checkout_available),
    checkout_service: CheckoutServiceInterface = Depends(get_checkout_service),
) -> CheckoutValidationResponse:
    return await checkout_service.validate_checkout(user_id=current_user.sub, req=req)
