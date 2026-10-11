import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository, AdminRepositoryInterface
from app.admin.schemas import (
    AdminAuditLogResponse,
    AdminCustomerDetailResponse,
    AdminCustomerResponse,
    AdminCustomerUpdateRequest,
    AdminMerchantResponse,
    AdminSetPasswordRequest,
    AdminSetPasswordResponse,
    AdminSubscriptionModifyRequest,
    AdminSubscriptionResponse,
    BannerCreate,
    BannerResponse,
    BranchManagerAssignRequest,
    BranchManagerCreateRequest,
    BranchManagerResponse,
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
        customer_repo=customer_repo,
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


@router.get(
    "/merchants",
    response_model=list[AdminMerchantResponse],
    status_code=status.HTTP_200_OK,
    summary="List merchants with owner details and verification status",
)
async def list_merchants(
    status: str | None = Query(
        None,
        description="Optional status filter (e.g. DRAFT, PENDING, APPROVED, REJECTED)",
    ),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminMerchantResponse]:
    return await admin_service.list_merchants(status=status)


@router.get(
    "/subscriptions",
    response_model=list[AdminSubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List all merchant subscriptions with filters",
    description="Retrieve all subscriptions across merchants with optional filtering by merchant_id, status, and plan_tier.",
)
async def list_subscriptions(
    merchant_id: uuid.UUID | None = Query(
        None, description="Optional merchant ID filter"
    ),
    status: str | None = Query(
        None,
        description="Optional status filter ('ACTIVE', 'SUPERSEDED', 'CANCELLED', etc.)",
    ),
    plan_tier: str | None = Query(
        None, description="Optional tier filter ('BASIC', 'PROFESSIONAL', 'ENTERPRISE')"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminSubscriptionResponse]:
    return await admin_service.list_subscriptions(
        merchant_id=merchant_id,
        status=status,
        plan_tier=plan_tier,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/subscriptions/history",
    response_model=list[AdminSubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get subscription change history",
    description="Retrieve historical subscription transitions and changes across all merchants or filtered by merchant_id.",
)
async def get_subscription_history(
    merchant_id: uuid.UUID | None = Query(
        None, description="Optional merchant ID filter"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminSubscriptionResponse]:
    return await admin_service.get_subscription_history(
        merchant_id=merchant_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/merchants/{merchant_id}/subscriptions",
    response_model=list[AdminSubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get merchant subscription history",
    description="Retrieve all previous and current subscription history records for a specific merchant.",
)
async def get_merchant_subscription_history(
    merchant_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminSubscriptionResponse]:
    return await admin_service.get_subscription_history(
        merchant_id=merchant_id,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=AdminSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Modify subscription",
    description="Directly modify a merchant's subscription parameters (tier, cycle, status, commission rate, valid_until).",
)
async def modify_subscription(
    subscription_id: uuid.UUID,
    req: AdminSubscriptionModifyRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> AdminSubscriptionResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.modify_subscription(
        subscription_id=subscription_id,
        req=req,
        admin_user_id=uuid.UUID(current_user.sub),
        ip_address=ip,
    )


@router.put(
    "/merchants/{merchant_id}/subscription",
    response_model=AdminSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Set or override merchant subscription",
    description="Modify the active subscription or create/assign a new subscription for a merchant with custom terms.",
)
@router.patch(
    "/merchants/{merchant_id}/subscription",
    response_model=AdminSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Modify merchant subscription",
    description="Modify the active subscription or create/assign a new subscription for a merchant with custom terms.",
)
async def modify_merchant_subscription(
    merchant_id: uuid.UUID,
    req: AdminSubscriptionModifyRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> AdminSubscriptionResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.modify_merchant_subscription(
        merchant_id=merchant_id,
        req=req,
        admin_user_id=uuid.UUID(current_user.sub),
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


@router.post(
    "/branch-managers",
    response_model=BranchManagerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a BranchManager bound to a specific branch",
)
async def create_branch_manager(
    req: BranchManagerCreateRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> BranchManagerResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.create_branch_manager(
        admin_user_id=uuid.UUID(current_user.sub), req=req, ip_address=ip
    )


@router.get(
    "/branch-managers",
    response_model=list[BranchManagerResponse],
    status_code=status.HTTP_200_OK,
    summary="List BranchManagers with their branch IDs",
)
async def list_branch_managers(
    branch_id: uuid.UUID | None = Query(None),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[BranchManagerResponse]:
    return await admin_service.list_branch_managers(branch_id=branch_id)


@router.put(
    "/branch-managers/{user_id}/branch",
    response_model=BranchManagerResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign or move an existing BranchManager to a branch",
)
async def assign_branch_manager(
    user_id: uuid.UUID,
    req: BranchManagerAssignRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> BranchManagerResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.assign_branch_manager(
        admin_user_id=uuid.UUID(current_user.sub),
        user_id=user_id,
        branch_id=req.branch_id,
        ip_address=ip,
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


@router.post(
    "/set-password",
    response_model=AdminSetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin set user password",
    description="Administrator directly sets or overrides the password for any user account using user_id or email.",
)
async def admin_set_password(
    req: AdminSetPasswordRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> AdminSetPasswordResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.set_user_password(
        admin_user_id=uuid.UUID(current_user.sub),
        req=req,
        ip_address=ip,
    )


@router.get(
    "/customers",
    response_model=list[AdminCustomerResponse],
    status_code=status.HTTP_200_OK,
    summary="List customers with filters and pagination",
    description="Retrieve customers with optional search across name/email/phone, filter by active status, and pagination.",
)
async def list_customers(
    search: str | None = Query(
        None, description="Search by name, email, or phone number"
    ),
    is_active: bool | None = Query(
        None, description="Filter by active/inactive account status"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> list[AdminCustomerResponse]:
    return await admin_service.list_customers(
        search=search, is_active=is_active, skip=skip, limit=limit
    )


@router.get(
    "/customers/{customer_id}",
    response_model=AdminCustomerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer details",
    description="Retrieve detailed customer profile including delivery addresses and order summary stats.",
)
async def get_customer(
    customer_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> AdminCustomerDetailResponse:
    return await admin_service.get_customer(customer_id=customer_id)


@router.patch(
    "/customers/{customer_id}",
    response_model=AdminCustomerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update customer profile and account status",
    description="Update customer profile information and toggle account active/verified status.",
)
async def update_customer(
    customer_id: uuid.UUID,
    req: AdminCustomerUpdateRequest,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    admin_service: AdminServiceInterface = Depends(get_admin_service),
) -> AdminCustomerDetailResponse:
    ip = request.client.host if request.client else "127.0.0.1"
    return await admin_service.update_customer(
        customer_id=customer_id,
        req=req,
        admin_user_id=uuid.UUID(current_user.sub),
        ip_address=ip,
    )

