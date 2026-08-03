import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository, AdminRepositoryInterface
from app.admin.schemas import (
    AdminAuditLogResponse,
    BannerCreate,
    BannerResponse,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    MerchantApprovalRequest,
    PlatformAnalyticsOverview,
    RefundOverrideRequest,
    RefundOverrideResponse,
)
from app.admin.service import AdminService, AdminServiceInterface
from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.coupon.repository import CouponRepository
from app.coupon.schemas import CouponCreate, CouponResponse
from app.coupon.service import CouponService
from app.customer.repository import CustomerRepository
from app.merchant.repository import MerchantRepository, MerchantRepositoryInterface

router = APIRouter(prefix="/admin", tags=["Admin Subsystem"])


def get_admin_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AdminRepositoryInterface:
    return AdminRepository(session=session)


def get_merchant_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantRepositoryInterface:
    return MerchantRepository(session=session)


def get_admin_service(
    session: AsyncSession = Depends(get_db_session),
    admin_repo: AdminRepositoryInterface = Depends(get_admin_repository),
    merchant_repo: MerchantRepositoryInterface = Depends(get_merchant_repository),
) -> AdminServiceInterface:
    coupon_repo = CouponRepository(session=session)
    customer_repo = CustomerRepository(session=session)
    coupon_service = CouponService(
        session=session, coupon_repo=coupon_repo, customer_repo=customer_repo
    )
    return AdminService(
        session=session,
        admin_repo=admin_repo,
        merchant_repo=merchant_repo,
        coupon_service=coupon_service,
    )


@router.post(
    "/merchants/{merchant_id}/approval",
    status_code=status.HTTP_200_OK,
    summary="Approve or reject merchant onboarding application",
)
async def approve_or_reject_merchant(
    merchant_id: uuid.UUID,
    req: MerchantApprovalRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> dict:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.approve_or_reject_merchant(
        admin_user_id=uuid.UUID(current_user.sub),
        merchant_id=merchant_id,
        req=req,
        ip_address=ip,
    )


@router.post(
    "/coupons",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create global platform or restaurant coupon via Admin CMS",
)
async def admin_create_coupon(
    req: CouponCreate,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> CouponResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.admin_create_coupon(
        admin_user_id=uuid.UUID(current_user.sub), req=req, ip_address=ip
    )


@router.post(
    "/banners",
    response_model=BannerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create marketing banner for app homepage",
)
async def create_banner(
    req: BannerCreate,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> BannerResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.create_banner(
        admin_user_id=uuid.UUID(current_user.sub), req=req, ip_address=ip
    )


@router.get(
    "/banners",
    response_model=list[BannerResponse],
    status_code=status.HTTP_200_OK,
    summary="List marketing banners",
)
async def list_banners(
    active_only: bool = Query(True),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[BannerResponse]:
    return await admin_service.get_banners(active_only=active_only)


@router.delete(
    "/banners/{banner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete marketing banner",
)
async def delete_banner(
    banner_id: uuid.UUID,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> None:
    ip = request.client.host if request.client else "127.0.0.1"
    await admin_service.delete_banner(
        admin_user_id=uuid.UUID(current_user.sub), banner_id=banner_id, ip_address=ip
    )


@router.get(
    "/feature-flags",
    response_model=list[FeatureFlagResponse],
    status_code=status.HTTP_200_OK,
    summary="Get system feature flags & operational throttles",
)
async def get_feature_flags(
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[FeatureFlagResponse]:
    return await admin_service.get_feature_flags()


@router.put(
    "/feature-flags/{flag_key}",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle system feature flag or throttle threshold",
)
async def update_feature_flag(
    flag_key: str,
    req: FeatureFlagUpdate,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> FeatureFlagResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.update_feature_flag(
        admin_user_id=uuid.UUID(current_user.sub),
        flag_key=flag_key,
        req=req,
        ip_address=ip,
    )


@router.post(
    "/refunds/override",
    response_model=RefundOverrideResponse,
    status_code=status.HTTP_200_OK,
    summary="Authorize and issue manual admin refund override",
)
async def issue_refund_override(
    req: RefundOverrideRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> RefundOverrideResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.issue_refund_override(
        admin_user_id=uuid.UUID(current_user.sub), req=req, ip_address=ip
    )


@router.get(
    "/audit-logs",
    response_model=list[AdminAuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get immutable platform admin audit logs",
)
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminAuditLogResponse]:
    return await admin_service.get_audit_logs(limit=limit)


@router.get(
    "/analytics/overview",
    response_model=PlatformAnalyticsOverview,
    status_code=status.HTTP_200_OK,
    summary="Get platform operational analytics & revenue overview",
)
async def get_analytics_overview(
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> PlatformAnalyticsOverview:
    return await admin_service.get_analytics_overview()
