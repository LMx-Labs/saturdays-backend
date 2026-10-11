import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditLog, Banner
from app.admin.repository import AdminRepositoryInterface
from app.admin.schemas import (
    AdminAuditLogResponse,
    AdminCustomerAddressResponse,
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
    BranchManagerCreateRequest,
    BranchManagerResponse,
    FeatureFlagResponse,
    FeatureFlagUpdate,
    MerchantApprovalRequest,
    PlatformAnalyticsOverview,
    RefundOverrideRequest,
    RefundOverrideResponse,
)
from app.auth.models import User
from app.branch.models import Branch
from app.core.exceptions import (
    ConflictError,
    DomainInvariantError,
    EntityNotFoundError,
    UnprocessableEntityError,
)
from app.core.security import hash_password
from app.coupon.schemas import CouponCreate, CouponResponse
from app.coupon.service import CouponServiceInterface
from app.customer.repository import (
    CustomerRepository,
    CustomerRepositoryInterface,
)
from app.merchant.models import Merchant
from app.merchant.repository import MerchantRepositoryInterface
from app.payment.service import ensure_refunds_enabled
from app.subscription.models import MerchantSubscription
from app.subscription.repository import (
    SubscriptionRepository,
    SubscriptionRepositoryInterface,
)
from app.subscription.service import PLAN_DETAILS

# In-memory operational system feature flags
SYSTEM_FEATURE_FLAGS: dict[str, dict[str, Any]] = {
    "EMERGENCY_MAINTENANCE_MODE": {
        "enabled": False,
        "value": None,
        "description": "Halts customer checkout globally across Saturdays during major campus disruptions.",
    },
    "MAX_CAMPUS_ORDERS_PER_HOUR": {
        "enabled": True,
        "value": "500",
        "description": "Dynamic throttle cap preventing store overload during campus events.",
    },
}


class AdminServiceInterface(ABC):
    @abstractmethod
    async def approve_or_reject_merchant(
        self,
        admin_user_id: uuid.UUID,
        merchant_id: uuid.UUID,
        req: MerchantApprovalRequest,
        ip_address: str = "127.0.0.1",
    ) -> dict:
        pass

    @abstractmethod
    async def list_merchants(
        self, status: str | None = None
    ) -> list[AdminMerchantResponse]:
        pass

    @abstractmethod
    async def admin_create_coupon(
        self, admin_user_id: uuid.UUID, req: CouponCreate, ip_address: str = "127.0.0.1"
    ) -> CouponResponse:
        pass

    @abstractmethod
    async def create_banner(
        self, admin_user_id: uuid.UUID, req: BannerCreate, ip_address: str = "127.0.0.1"
    ) -> BannerResponse:
        pass

    @abstractmethod
    async def get_banners(self, active_only: bool = True) -> list[BannerResponse]:
        pass

    @abstractmethod
    async def delete_banner(
        self,
        admin_user_id: uuid.UUID,
        banner_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> None:
        pass

    @abstractmethod
    async def get_feature_flags(self) -> list[FeatureFlagResponse]:
        pass

    @abstractmethod
    async def update_feature_flag(
        self,
        admin_user_id: uuid.UUID,
        flag_key: str,
        req: FeatureFlagUpdate,
        ip_address: str = "127.0.0.1",
    ) -> FeatureFlagResponse:
        pass

    @abstractmethod
    async def issue_refund_override(
        self,
        admin_user_id: uuid.UUID,
        req: RefundOverrideRequest,
        ip_address: str = "127.0.0.1",
    ) -> RefundOverrideResponse:
        pass

    @abstractmethod
    async def create_branch_manager(
        self,
        admin_user_id: uuid.UUID,
        req: BranchManagerCreateRequest,
        ip_address: str = "127.0.0.1",
    ) -> BranchManagerResponse:
        pass

    @abstractmethod
    async def assign_branch_manager(
        self,
        admin_user_id: uuid.UUID,
        user_id: uuid.UUID,
        branch_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> BranchManagerResponse:
        pass

    @abstractmethod
    async def list_branch_managers(
        self, branch_id: uuid.UUID | None = None
    ) -> list[BranchManagerResponse]:
        pass

    @abstractmethod
    async def get_audit_logs(self, limit: int = 50) -> list[AdminAuditLogResponse]:
        pass

    @abstractmethod
    async def get_analytics_overview(self) -> PlatformAnalyticsOverview:
        pass

    @abstractmethod
    async def set_user_password(
        self,
        admin_user_id: uuid.UUID,
        req: AdminSetPasswordRequest,
        target_user_id: uuid.UUID | None = None,
        ip_address: str = "127.0.0.1",
    ) -> AdminSetPasswordResponse:
        pass

    @abstractmethod
    async def list_subscriptions(
        self,
        merchant_id: uuid.UUID | None = None,
        status: str | None = None,
        plan_tier: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AdminSubscriptionResponse]:
        pass

    @abstractmethod
    async def get_subscription_history(
        self,
        merchant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AdminSubscriptionResponse]:
        pass

    @abstractmethod
    async def modify_subscription(
        self,
        subscription_id: uuid.UUID,
        req: AdminSubscriptionModifyRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminSubscriptionResponse:
        pass

    @abstractmethod
    async def modify_merchant_subscription(
        self,
        merchant_id: uuid.UUID,
        req: AdminSubscriptionModifyRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminSubscriptionResponse:
        pass

    @abstractmethod
    async def list_customers(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AdminCustomerResponse]:
        pass

    @abstractmethod
    async def get_customer(
        self, customer_id: uuid.UUID
    ) -> AdminCustomerDetailResponse:
        pass

    @abstractmethod
    async def update_customer(
        self,
        customer_id: uuid.UUID,
        req: AdminCustomerUpdateRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminCustomerDetailResponse:
        pass


class AdminService(AdminServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        admin_repo: AdminRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
        coupon_service: CouponServiceInterface,
        sub_repo: SubscriptionRepositoryInterface | None = None,
        customer_repo: CustomerRepositoryInterface | None = None,
    ):
        self.session = session
        self.admin_repo = admin_repo
        self.merchant_repo = merchant_repo
        self.coupon_service = coupon_service
        self.sub_repo = sub_repo or SubscriptionRepository(session=session)
        self.customer_repo = customer_repo or CustomerRepository(session=session)

    async def _write_audit_log(
        self,
        admin_user_id: uuid.UUID,
        action: str,
        target_entity: str,
        target_entity_id: uuid.UUID | None,
        changes_payload: dict,
        ip_address: str,
    ) -> None:
        audit = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_entity=target_entity,
            target_entity_id=target_entity_id,
            changes_payload=changes_payload,
            ip_address=ip_address,
        )
        await self.admin_repo.log_action(audit)

    async def approve_or_reject_merchant(
        self,
        admin_user_id: uuid.UUID,
        merchant_id: uuid.UUID,
        req: MerchantApprovalRequest,
        ip_address: str = "127.0.0.1",
    ) -> dict:
        action_upper = req.action.upper()
        if action_upper not in ("APPROVE", "REJECT"):
            raise UnprocessableEntityError(
                message="Action must be either 'APPROVE' or 'REJECT'.",
                error_code="INVALID_APPROVAL_ACTION",
            )

        merchant = await self.merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise EntityNotFoundError(
                message="Merchant not found.", error_code="MERCHANT_NOT_FOUND"
            )

        new_status = "APPROVED" if action_upper == "APPROVE" else "REJECTED"
        merchant.status = new_status
        await self.merchant_repo.update(merchant)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action=f"MERCHANT_{new_status}",
            target_entity="merchants",
            target_entity_id=merchant.id,
            changes_payload={
                "action": req.action,
                "reason": req.reason,
                "new_status": new_status,
            },
            ip_address=ip_address,
        )

        await self.session.commit()
        return {
            "merchant_id": str(merchant.id),
            "status": new_status,
            "message": f"Merchant has been {new_status.lower()}.",
        }

    @staticmethod
    def _to_admin_merchant_response(
        merchant: Merchant, owner: User
    ) -> AdminMerchantResponse:
        return AdminMerchantResponse(
            id=merchant.id,
            owner_user_id=merchant.owner_user_id,
            owner_email=owner.email,
            business_name=merchant.business_name,
            legal_entity_name=merchant.legal_entity_name,
            gstin=merchant.gstin,
            fssai_license_number=merchant.fssai_license_number,
            bank_account_number=merchant.bank_account_number,
            bank_ifsc_code=merchant.bank_ifsc_code,
            status=merchant.status,
            created_at=merchant.created_at,
            updated_at=merchant.updated_at,
        )

    async def list_merchants(
        self, status: str | None = None
    ) -> list[AdminMerchantResponse]:
        stmt = (
            select(Merchant, User)
            .join(User, User.id == Merchant.owner_user_id)
            .where(Merchant.deleted_at.is_(None))
            .order_by(Merchant.created_at.desc())
        )
        if status:
            stmt = stmt.where(func.upper(Merchant.status) == status.strip().upper())
        res = await self.session.execute(stmt)
        return [self._to_admin_merchant_response(m, u) for m, u in res.all()]

    async def admin_create_coupon(
        self, admin_user_id: uuid.UUID, req: CouponCreate, ip_address: str = "127.0.0.1"
    ) -> CouponResponse:
        coupon_res = await self.coupon_service.create_coupon(req)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="COUPON_CREATED",
            target_entity="coupons",
            target_entity_id=coupon_res.id,
            changes_payload=req.model_dump(mode="json"),
            ip_address=ip_address,
        )
        await self.session.commit()
        return coupon_res

    async def create_banner(
        self, admin_user_id: uuid.UUID, req: BannerCreate, ip_address: str = "127.0.0.1"
    ) -> BannerResponse:
        banner = Banner(
            title=req.title,
            image_url=req.image_url,
            target_url=req.target_url,
            display_order=req.display_order,
            is_active=req.is_active,
        )
        created = await self.admin_repo.create_banner(banner)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="BANNER_CREATED",
            target_entity="banners",
            target_entity_id=created.id,
            changes_payload=req.model_dump(mode="json"),
            ip_address=ip_address,
        )
        await self.session.commit()
        return BannerResponse.model_validate(created)

    async def get_banners(self, active_only: bool = True) -> list[BannerResponse]:
        banners = await self.admin_repo.get_banners(active_only=active_only)
        return [BannerResponse.model_validate(b) for b in banners]

    async def delete_banner(
        self,
        admin_user_id: uuid.UUID,
        banner_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> None:
        await self.admin_repo.delete_banner(banner_id)
        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="BANNER_DELETED",
            target_entity="banners",
            target_entity_id=banner_id,
            changes_payload={"banner_id": str(banner_id)},
            ip_address=ip_address,
        )
        await self.session.commit()

    async def get_feature_flags(self) -> list[FeatureFlagResponse]:
        return [
            FeatureFlagResponse(flag_key=k, enabled=v["enabled"], value=v.get("value"))
            for k, v in SYSTEM_FEATURE_FLAGS.items()
        ]

    async def update_feature_flag(
        self,
        admin_user_id: uuid.UUID,
        flag_key: str,
        req: FeatureFlagUpdate,
        ip_address: str = "127.0.0.1",
    ) -> FeatureFlagResponse:
        if flag_key not in SYSTEM_FEATURE_FLAGS:
            SYSTEM_FEATURE_FLAGS[flag_key] = {
                "enabled": req.enabled,
                "value": req.value,
                "description": "Custom system feature flag",
            }
        else:
            SYSTEM_FEATURE_FLAGS[flag_key]["enabled"] = req.enabled
            SYSTEM_FEATURE_FLAGS[flag_key]["value"] = req.value

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="FEATURE_FLAG_TOGGLED",
            target_entity="system",
            target_entity_id=None,
            changes_payload={
                "flag_key": flag_key,
                "enabled": req.enabled,
                "value": req.value,
            },
            ip_address=ip_address,
        )
        await self.session.commit()

        return FeatureFlagResponse(
            flag_key=flag_key,
            enabled=req.enabled,
            value=req.value,
        )

    async def issue_refund_override(
        self,
        admin_user_id: uuid.UUID,
        req: RefundOverrideRequest,
        ip_address: str = "127.0.0.1",
    ) -> RefundOverrideResponse:
        ensure_refunds_enabled()
        refund_tx_id = f"ref_override_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="MANUAL_REFUND_ISSUED",
            target_entity="payments",
            target_entity_id=req.payment_id,
            changes_payload={
                "refund_transaction_id": refund_tx_id,
                "amount": req.amount,
                "reason": req.reason,
            },
            ip_address=ip_address,
        )
        await self.session.commit()

        return RefundOverrideResponse(
            refund_transaction_id=refund_tx_id,
            payment_id=req.payment_id,
            amount=req.amount,
            status="PROCESSED",
            reason=req.reason,
            processed_at=now,
        )

    async def _get_active_branch(self, branch_id: uuid.UUID) -> Branch:
        res = await self.session.execute(
            select(Branch).where(Branch.id == branch_id, Branch.deleted_at.is_(None))
        )
        branch = res.scalars().first()
        if not branch:
            raise EntityNotFoundError(
                message=f"Branch '{branch_id}' not found.",
                error_code="BRANCH_NOT_FOUND",
            )
        return branch

    @staticmethod
    def _to_manager_response(user: User, branch: Branch) -> BranchManagerResponse:
        return BranchManagerResponse(
            user_id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            branch_id=branch.id,
            branch_name=branch.name,
            brand_id=branch.brand_id,
        )

    async def create_branch_manager(
        self,
        admin_user_id: uuid.UUID,
        req: BranchManagerCreateRequest,
        ip_address: str = "127.0.0.1",
    ) -> BranchManagerResponse:
        branch = await self._get_active_branch(req.branch_id)

        email = req.email.strip().lower()
        existing = await self.session.execute(
            select(User.id).where(
                func.lower(User.email) == email, User.deleted_at.is_(None)
            )
        )
        if existing.first():
            raise ConflictError(
                message="User with this email already exists.",
                error_code="EMAIL_ALREADY_EXISTS",
            )

        user = User(
            email=email,
            password_hash=hash_password(req.password),
            role="BranchManager",
            branch_id=branch.id,
            is_active=True,
            is_verified=True,
        )
        self.session.add(user)
        await self.session.flush()

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="BRANCH_MANAGER_CREATED",
            target_entity="users",
            target_entity_id=user.id,
            changes_payload={"email": email, "branch_id": str(branch.id)},
            ip_address=ip_address,
        )
        await self.session.commit()
        return self._to_manager_response(user, branch)

    async def assign_branch_manager(
        self,
        admin_user_id: uuid.UUID,
        user_id: uuid.UUID,
        branch_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> BranchManagerResponse:
        branch = await self._get_active_branch(branch_id)
        res = await self.session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = res.scalars().first()
        if not user or user.role != "BranchManager":
            raise EntityNotFoundError(
                message="Branch manager not found.",
                error_code="BRANCH_MANAGER_NOT_FOUND",
            )

        previous = str(user.branch_id) if user.branch_id else None
        user.branch_id = branch.id
        await self.session.flush()

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="BRANCH_MANAGER_REASSIGNED",
            target_entity="users",
            target_entity_id=user.id,
            changes_payload={
                "from_branch_id": previous,
                "to_branch_id": str(branch.id),
            },
            ip_address=ip_address,
        )
        await self.session.commit()
        return self._to_manager_response(user, branch)

    async def list_branch_managers(
        self, branch_id: uuid.UUID | None = None
    ) -> list[BranchManagerResponse]:
        stmt = (
            select(User, Branch)
            .join(Branch, Branch.id == User.branch_id)
            .where(User.role == "BranchManager", User.deleted_at.is_(None))
            .order_by(Branch.name, User.email)
        )
        if branch_id:
            stmt = stmt.where(User.branch_id == branch_id)
        res = await self.session.execute(stmt)
        return [self._to_manager_response(u, b) for u, b in res.all()]

    async def get_audit_logs(self, limit: int = 50) -> list[AdminAuditLogResponse]:
        logs = await self.admin_repo.get_audit_logs(limit=limit)
        return [AdminAuditLogResponse.model_validate(l) for l in logs]

    async def get_analytics_overview(self) -> PlatformAnalyticsOverview:
        stats = await self.admin_repo.get_analytics_overview()
        return PlatformAnalyticsOverview(**stats)

    async def set_user_password(
        self,
        admin_user_id: uuid.UUID,
        req: AdminSetPasswordRequest,
        target_user_id: uuid.UUID | None = None,
        ip_address: str = "127.0.0.1",
    ) -> AdminSetPasswordResponse:
        user_id = target_user_id or req.user_id
        email = req.email

        stmt = select(User).where(User.deleted_at.is_(None))
        if user_id:
            stmt = stmt.where(User.id == user_id)
        elif email:
            stmt = stmt.where(func.lower(User.email) == email.strip().lower())
        else:
            raise DomainInvariantError(
                message="Either user_id or email must be provided to set user password.",
                error_code="MISSING_USER_IDENTIFIER",
            )

        res = await self.session.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise EntityNotFoundError(
                message="User not found.",
                error_code="USER_NOT_FOUND",
            )

        # Hash new password with Argon2id (INV-AUTH-002)
        user.password_hash = hash_password(req.password)  # type: ignore[arg-type]
        await self.session.flush()

        # Audit log the admin password override (never logging the password)
        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="USER_PASSWORD_SET_BY_ADMIN",
            target_entity="users",
            target_entity_id=user.id,
            changes_payload={"email": user.email, "user_id": str(user.id)},
            ip_address=ip_address,
        )
        await self.session.commit()

        return AdminSetPasswordResponse(
            message="Password has been successfully updated by administrator.",
            user_id=user.id,
            email=user.email,
        )

    def _to_admin_sub_response(
        self, sub: MerchantSubscription
    ) -> AdminSubscriptionResponse:
        tier_info = PLAN_DETAILS.get(sub.plan_tier, PLAN_DETAILS["BASIC"])
        business_name = sub.merchant.business_name if sub.merchant else None
        return AdminSubscriptionResponse(
            id=sub.id,
            merchant_id=sub.merchant_id,
            business_name=business_name,
            merchant_name=business_name,
            plan_tier=sub.plan_tier,
            billing_cycle=sub.billing_cycle,
            status=sub.status,
            commission_rate_percentage=float(sub.commission_rate_percentage),
            max_branches=int(tier_info["max_branches"]),
            valid_until=sub.valid_until,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )

    async def list_subscriptions(
        self,
        merchant_id: uuid.UUID | None = None,
        status: str | None = None,
        plan_tier: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AdminSubscriptionResponse]:
        subs = await self.sub_repo.list_subscriptions(
            merchant_id=merchant_id,
            status=status,
            plan_tier=plan_tier,
            skip=skip,
            limit=limit,
        )
        return [self._to_admin_sub_response(s) for s in subs]

    async def get_subscription_history(
        self,
        merchant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AdminSubscriptionResponse]:
        if merchant_id:
            merchant = await self.merchant_repo.get_by_id(merchant_id)
            if not merchant:
                raise EntityNotFoundError(
                    message="Merchant not found.", error_code="MERCHANT_NOT_FOUND"
                )
        subs = await self.sub_repo.get_subscription_history(
            merchant_id=merchant_id,
            skip=skip,
            limit=limit,
        )
        return [self._to_admin_sub_response(s) for s in subs]

    async def modify_subscription(
        self,
        subscription_id: uuid.UUID,
        req: AdminSubscriptionModifyRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminSubscriptionResponse:
        sub = await self.sub_repo.get_subscription_by_id(subscription_id)
        if not sub:
            raise EntityNotFoundError(
                message=f"Subscription '{subscription_id}' not found.",
                error_code="SUBSCRIPTION_NOT_FOUND",
            )

        update_data: dict[str, Any] = {}
        if req.plan_tier is not None:
            tier = req.plan_tier.upper()
            if tier not in PLAN_DETAILS:
                raise UnprocessableEntityError(
                    message=f"Invalid plan tier '{req.plan_tier}'. Must be BASIC, PROFESSIONAL, or ENTERPRISE.",
                    error_code="INVALID_PLAN_TIER",
                )
            update_data["plan_tier"] = tier
            if req.commission_rate_percentage is None:
                update_data["commission_rate_percentage"] = PLAN_DETAILS[tier][
                    "commission_rate"
                ]

        if req.commission_rate_percentage is not None:
            update_data["commission_rate_percentage"] = req.commission_rate_percentage

        if req.billing_cycle is not None:
            cycle = req.billing_cycle.upper()
            if cycle not in ("MONTHLY", "ANNUAL"):
                raise UnprocessableEntityError(
                    message=f"Invalid billing cycle '{req.billing_cycle}'. Must be MONTHLY or ANNUAL.",
                    error_code="INVALID_BILLING_CYCLE",
                )
            update_data["billing_cycle"] = cycle

        if req.status is not None:
            status_val = req.status.upper()
            valid_statuses = (
                "ACTIVE",
                "CANCELLED",
                "SUSPENDED",
                "EXPIRED",
                "SUPERSEDED",
            )
            if status_val not in valid_statuses:
                raise UnprocessableEntityError(
                    message=f"Invalid subscription status '{req.status}'.",
                    error_code="INVALID_SUBSCRIPTION_STATUS",
                )
            update_data["status"] = status_val

            # If setting to ACTIVE, supersede any other active subscriptions for this merchant
            if status_val == "ACTIVE":
                active_sub = await self.sub_repo.get_active_subscription(
                    sub.merchant_id
                )
                if active_sub and active_sub.id != sub.id:
                    await self.sub_repo.update_subscription(
                        active_sub, {"status": "SUPERSEDED"}
                    )

        if req.valid_until is not None:
            update_data["valid_until"] = req.valid_until
        elif req.duration_months is not None:
            now = datetime.now(UTC)
            current_expiry = (
                sub.valid_until
                if sub.valid_until.tzinfo
                else sub.valid_until.replace(tzinfo=UTC)
            )
            base_time = max(now, current_expiry)
            update_data["valid_until"] = base_time + timedelta(
                days=30 * req.duration_months
            )

        await self.sub_repo.update_subscription(sub, update_data)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="SUBSCRIPTION_MODIFIED",
            target_entity="merchant_subscriptions",
            target_entity_id=sub.id,
            changes_payload={
                "merchant_id": str(sub.merchant_id),
                "updates": {
                    k: str(v) if isinstance(v, datetime) else v
                    for k, v in update_data.items()
                },
                "reason": req.reason,
            },
            ip_address=ip_address,
        )

        await self.session.commit()
        self.session.expire_all()

        refreshed = await self.sub_repo.get_subscription_by_id(subscription_id)
        assert refreshed is not None
        return self._to_admin_sub_response(refreshed)

    async def modify_merchant_subscription(
        self,
        merchant_id: uuid.UUID,
        req: AdminSubscriptionModifyRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminSubscriptionResponse:
        merchant = await self.merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise EntityNotFoundError(
                message="Merchant not found.", error_code="MERCHANT_NOT_FOUND"
            )

        active_sub = await self.sub_repo.get_active_subscription(merchant_id)
        if active_sub:
            return await self.modify_subscription(
                subscription_id=active_sub.id,
                req=req,
                admin_user_id=admin_user_id,
                ip_address=ip_address,
            )

        # No active subscription: create a new one with the requested details
        tier = req.plan_tier.upper() if req.plan_tier else "BASIC"
        if tier not in PLAN_DETAILS:
            raise UnprocessableEntityError(
                message=f"Invalid plan tier '{req.plan_tier}'. Must be BASIC, PROFESSIONAL, or ENTERPRISE.",
                error_code="INVALID_PLAN_TIER",
            )
        tier_info = PLAN_DETAILS[tier]
        cycle = req.billing_cycle.upper() if req.billing_cycle else "MONTHLY"
        if cycle not in ("MONTHLY", "ANNUAL"):
            raise UnprocessableEntityError(
                message=f"Invalid billing cycle '{req.billing_cycle}'. Must be MONTHLY or ANNUAL.",
                error_code="INVALID_BILLING_CYCLE",
            )

        rate = (
            req.commission_rate_percentage
            if req.commission_rate_percentage is not None
            else tier_info["commission_rate"]
        )
        status_val = req.status.upper() if req.status else "ACTIVE"

        now = datetime.now(UTC)
        if req.valid_until is not None:
            valid_until = req.valid_until
        elif req.duration_months is not None:
            valid_until = now + timedelta(days=30 * req.duration_months)
        elif cycle == "ANNUAL":
            valid_until = now + timedelta(days=365)
        else:
            valid_until = now + timedelta(days=30)

        new_sub = MerchantSubscription(
            merchant_id=merchant_id,
            plan_tier=tier,
            billing_cycle=cycle,
            status=status_val,
            commission_rate_percentage=rate,
            valid_until=valid_until,
        )
        created_sub = await self.sub_repo.create_subscription(new_sub)

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="SUBSCRIPTION_CREATED",
            target_entity="merchant_subscriptions",
            target_entity_id=created_sub.id,
            changes_payload={
                "merchant_id": str(merchant_id),
                "plan_tier": tier,
                "billing_cycle": cycle,
                "status": status_val,
                "commission_rate_percentage": rate,
                "reason": req.reason,
            },
            ip_address=ip_address,
        )

        sub_id = created_sub.id
        await self.session.commit()
        self.session.expire_all()

        refreshed = await self.sub_repo.get_subscription_by_id(sub_id)
        assert refreshed is not None
        return self._to_admin_sub_response(refreshed)

    async def list_customers(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AdminCustomerResponse]:
        customers = await self.customer_repo.list_customers(
            search=search, is_active=is_active, skip=skip, limit=limit
        )
        return [
            AdminCustomerResponse(
                id=c.id,
                user_id=c.user_id,
                email=c.user.email if c.user else "",
                full_name=c.full_name,
                phone_number=c.phone_number,
                is_active=c.user.is_active if c.user else True,
                is_verified=c.user.is_verified if c.user else False,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in customers
        ]

    async def get_customer(
        self, customer_id: uuid.UUID
    ) -> AdminCustomerDetailResponse:
        customer = await self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise EntityNotFoundError(
                message=f"Customer profile with id '{customer_id}' not found.",
                error_code="CUSTOMER_NOT_FOUND",
            )
        addresses = await self.customer_repo.get_addresses(customer.id)
        order_count, total_spent = await self.customer_repo.get_customer_order_stats(
            customer.id
        )
        return AdminCustomerDetailResponse(
            id=customer.id,
            user_id=customer.user_id,
            email=customer.user.email if customer.user else "",
            full_name=customer.full_name,
            phone_number=customer.phone_number,
            is_active=customer.user.is_active if customer.user else True,
            is_verified=customer.user.is_verified if customer.user else False,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            addresses=[
                AdminCustomerAddressResponse(
                    id=a.id,
                    address_line=a.address_line,
                    building_name=a.building_name,
                    campus_zone=a.campus_zone,
                    is_primary=a.is_primary,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                )
                for a in addresses
            ],
            total_orders=order_count,
            total_spent=total_spent,
        )

    async def update_customer(
        self,
        customer_id: uuid.UUID,
        req: AdminCustomerUpdateRequest,
        admin_user_id: uuid.UUID,
        ip_address: str = "127.0.0.1",
    ) -> AdminCustomerDetailResponse:
        customer = await self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise EntityNotFoundError(
                message=f"Customer profile with id '{customer_id}' not found.",
                error_code="CUSTOMER_NOT_FOUND",
            )

        changes: dict[str, Any] = {}

        # Profile fields
        profile_updates: dict[str, Any] = {}
        if req.full_name is not None and req.full_name != customer.full_name:
            profile_updates["full_name"] = req.full_name
            changes["full_name"] = {"old": customer.full_name, "new": req.full_name}
        if req.phone_number is not None and req.phone_number != customer.phone_number:
            profile_updates["phone_number"] = req.phone_number
            changes["phone_number"] = {
                "old": customer.phone_number,
                "new": req.phone_number,
            }

        if profile_updates:
            await self.customer_repo.update_profile(customer, profile_updates)

        # User fields
        if customer.user:
            user = customer.user
            if req.is_active is not None and req.is_active != user.is_active:
                changes["is_active"] = {"old": user.is_active, "new": req.is_active}
                user.is_active = req.is_active
            if req.is_verified is not None and req.is_verified != user.is_verified:
                changes["is_verified"] = {
                    "old": user.is_verified,
                    "new": req.is_verified,
                }
                user.is_verified = req.is_verified

        if changes:
            await self._write_audit_log(
                admin_user_id=admin_user_id,
                action="CUSTOMER_UPDATED",
                target_entity="customer_profiles",
                target_entity_id=customer.id,
                changes_payload=changes,
                ip_address=ip_address,
            )

        await self.session.commit()
        self.session.expire_all()

        return await self.get_customer(customer_id)

