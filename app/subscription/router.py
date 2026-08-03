import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface
from app.subscription.repository import (
    SubscriptionRepository,
    SubscriptionRepositoryInterface,
)
from app.subscription.schemas import (
    MerchantSubscriptionResponse,
    PlatformCommissionResponse,
    SubscriptionCreateRequest,
    SubscriptionInvoiceResponse,
    SubscriptionRenewalRequest,
)
from app.subscription.service import SubscriptionService, SubscriptionServiceInterface

router = APIRouter(prefix="/merchants/me", tags=["Subscription"])


def get_subscription_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionRepositoryInterface:
    return SubscriptionRepository(session=session)


def get_merchant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantRepositoryInterface:
    return MerchantRepository(session=session)


def get_subscription_service(
    session: AsyncSession = Depends(get_db_session),
    sub_repo: SubscriptionRepositoryInterface = Depends(get_subscription_repository),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> SubscriptionServiceInterface:
    return SubscriptionService(
        session=session, sub_repo=sub_repo, merchant_repo=merchant_repo
    )


@router.get(
    "/subscription",
    response_model=MerchantSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get merchant active subscription",
)
async def get_my_subscription(
    current_user: UserClaims = Depends(get_current_user),
    sub_service: SubscriptionServiceInterface = Depends(get_subscription_service),
) -> MerchantSubscriptionResponse:
    return await sub_service.get_active_subscription(
        user_id=uuid.UUID(current_user.sub)
    )


@router.post(
    "/subscription",
    response_model=MerchantSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update merchant subscription plan tier",
)
async def create_subscription(
    req: SubscriptionCreateRequest,
    current_user: UserClaims = Depends(get_current_user),
    sub_service: SubscriptionServiceInterface = Depends(get_subscription_service),
) -> MerchantSubscriptionResponse:
    return await sub_service.create_subscription(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.post(
    "/subscription/renew",
    response_model=MerchantSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Renew merchant subscription",
)
async def renew_subscription(
    req: SubscriptionRenewalRequest,
    current_user: UserClaims = Depends(get_current_user),
    sub_service: SubscriptionServiceInterface = Depends(get_subscription_service),
) -> MerchantSubscriptionResponse:
    return await sub_service.renew_subscription(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.get(
    "/commissions",
    response_model=list[PlatformCommissionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get merchant platform commission ledger",
)
async def get_my_commissions(
    current_user: UserClaims = Depends(get_current_user),
    sub_service: SubscriptionServiceInterface = Depends(get_subscription_service),
) -> list[PlatformCommissionResponse]:
    return await sub_service.get_merchant_commissions(
        user_id=uuid.UUID(current_user.sub)
    )


@router.get(
    "/invoices",
    response_model=list[SubscriptionInvoiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get merchant subscription invoices & receipts",
)
async def get_my_invoices(
    current_user: UserClaims = Depends(get_current_user),
    sub_service: SubscriptionServiceInterface = Depends(get_subscription_service),
) -> list[SubscriptionInvoiceResponse]:
    return await sub_service.get_merchant_invoices(user_id=uuid.UUID(current_user.sub))
