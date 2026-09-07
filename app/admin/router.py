import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository, AdminRepositoryInterface
from app.admin.schemas import (
    AdminAuditLogResponse,
    BannerCreate,
    BannerResponse,
    BannerUpdate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    MerchantApprovalRequest,
    MerchantAdminPage,
    MerchantAdminSummary,
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
from app.merchant.models import Merchant
from app.admin.models import AdminAuditLog, Banner

router = APIRouter(prefix="/admin", tags=["Admin Subsystem"])


def _mask(value: str | None, visible: int = 4) -> str | None:
    if not value:
        return None
    return "*" * max(0, len(value) - visible) + value[-visible:]


def _merchant_summary(merchant: Merchant) -> MerchantAdminSummary:
    return MerchantAdminSummary(
        id=merchant.id,
        business_name=merchant.business_name,
        legal_entity_name=merchant.legal_entity_name,
        status=merchant.status,
        gstin_masked=_mask(merchant.gstin),
        fssai_license_masked=_mask(merchant.fssai_license_number),
        bank_account_masked=_mask(merchant.bank_account_number),
        created_at=merchant.created_at,
    )


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


@router.get("/merchants", response_model=MerchantAdminPage)
async def list_admin_merchants(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None, min_length=1, max_length=100),
    _current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
) -> MerchantAdminPage:
    filters = [Merchant.deleted_at.is_(None)]
    if status_filter:
        filters.append(Merchant.status == status_filter.upper())
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(Merchant.business_name.ilike(term), Merchant.legal_entity_name.ilike(term))
        )
    total = await session.scalar(select(func.count(Merchant.id)).where(*filters)) or 0
    merchants = (
        (
            await session.execute(
                select(Merchant)
                .where(*filters)
                .order_by(Merchant.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return MerchantAdminPage(
        items=[_merchant_summary(item) for item in merchants],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/merchants/{merchant_id}", response_model=MerchantAdminSummary)
async def get_admin_merchant(
    merchant_id: uuid.UUID,
    _current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
) -> MerchantAdminSummary:
    merchant = await session.get(Merchant, merchant_id)
    if not merchant or merchant.deleted_at is not None:
        from app.core.exceptions import EntityNotFoundError

        raise EntityNotFoundError("Merchant not found.", "MERCHANT_NOT_FOUND")
    return _merchant_summary(merchant)


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


@router.patch("/banners/{banner_id}", response_model=BannerResponse)
async def update_banner(
    banner_id: uuid.UUID,
    req: BannerUpdate,
    request: Request,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
) -> BannerResponse:
    banner = await session.get(Banner, banner_id)
    if not banner:
        from app.core.exceptions import EntityNotFoundError

        raise EntityNotFoundError("Banner not found.", "BANNER_NOT_FOUND")
    changes = req.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(banner, field, value)
    session.add(
        AdminAuditLog(
            admin_user_id=uuid.UUID(current_user.sub),
            action="BANNER_UPDATED",
            target_entity="banners",
            target_entity_id=banner.id,
            changes_payload=changes,
            ip_address=request.client.host if request.client else "127.0.0.1",
        )
    )
    await session.commit()
    await session.refresh(banner)
    return BannerResponse.model_validate(banner)


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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    action: str | None = Query(None, max_length=100),
    target_entity: str | None = Query(None, max_length=100),
    _current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[AdminAuditLogResponse]:
    stmt = select(AdminAuditLog)
    if action:
        stmt = stmt.where(AdminAuditLog.action == action)
    if target_entity:
        stmt = stmt.where(AdminAuditLog.target_entity == target_entity)
    logs = (
        await session.execute(
            stmt.order_by(AdminAuditLog.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars()
    return [AdminAuditLogResponse.model_validate(log) for log in logs]


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
