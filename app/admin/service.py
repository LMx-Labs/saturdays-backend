import uuid
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditLog, Banner, FeatureFlag
from app.admin.repository import AdminRepositoryInterface
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
from app.core.exceptions import EntityNotFoundError, UnprocessableEntityError
from app.coupon.schemas import CouponCreate, CouponResponse
from app.coupon.service import CouponServiceInterface
from app.merchant.repository import MerchantRepositoryInterface

DEFAULT_FEATURE_FLAGS = {
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
    async def get_audit_logs(self, limit: int = 50) -> list[AdminAuditLogResponse]:
        pass

    @abstractmethod
    async def get_analytics_overview(self) -> PlatformAnalyticsOverview:
        pass


class AdminService(AdminServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        admin_repo: AdminRepositoryInterface,
        merchant_repo: MerchantRepositoryInterface,
        coupon_service: CouponServiceInterface,
    ):
        self.session = session
        self.admin_repo = admin_repo
        self.merchant_repo = merchant_repo
        self.coupon_service = coupon_service

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
        flags = await self.admin_repo.get_feature_flags()
        if not flags:
            for key, value in DEFAULT_FEATURE_FLAGS.items():
                await self.admin_repo.upsert_feature_flag(
                    FeatureFlag(key=key, enabled=value["enabled"], value=value.get("value"))
                )
            await self.session.commit()
            flags = await self.admin_repo.get_feature_flags()
        return [
            FeatureFlagResponse(flag_key=flag.key, enabled=flag.enabled, value=flag.value)
            for flag in flags
        ]

    async def update_feature_flag(
        self,
        admin_user_id: uuid.UUID,
        flag_key: str,
        req: FeatureFlagUpdate,
        ip_address: str = "127.0.0.1",
    ) -> FeatureFlagResponse:
        flag = await self.session.get(FeatureFlag, flag_key)
        if not flag:
            flag = FeatureFlag(key=flag_key)
        flag.enabled = req.enabled
        flag.value = req.value
        flag.updated_by_user_id = admin_user_id
        await self.admin_repo.upsert_feature_flag(flag)

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
        from app.payment.repository import PaymentRepository
        from app.payment.schemas import RefundCreateRequest
        from app.payment.service import PaymentService

        refund_tx = await PaymentService(
            self.session, PaymentRepository(self.session)
        ).refund_payment(
            req.payment_id,
            RefundCreateRequest(amount=req.amount, reason=req.reason),
        )
        now = refund_tx.created_at

        await self._write_audit_log(
            admin_user_id=admin_user_id,
            action="MANUAL_REFUND_ISSUED",
            target_entity="payments",
            target_entity_id=req.payment_id,
            changes_payload={
                "refund_transaction_id": str(refund_tx.id),
                "amount": req.amount,
                "reason": req.reason,
            },
            ip_address=ip_address,
        )
        await self.session.commit()

        return RefundOverrideResponse(
            refund_transaction_id=str(refund_tx.id),
            payment_id=req.payment_id,
            amount=req.amount,
            status="PROCESSED",
            reason=req.reason,
            processed_at=now,
        )

    async def get_audit_logs(self, limit: int = 50) -> list[AdminAuditLogResponse]:
        logs = await self.admin_repo.get_audit_logs(limit=limit)
        return [AdminAuditLogResponse.model_validate(log) for log in logs]

    async def get_analytics_overview(self) -> PlatformAnalyticsOverview:
        stats = await self.admin_repo.get_analytics_overview()
        return PlatformAnalyticsOverview(**stats)
