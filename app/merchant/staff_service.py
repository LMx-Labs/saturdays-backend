import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Invitation, User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, ForbiddenError, UnprocessableEntityError
from app.core.roles import STAFF_ROLES, normalize_role
from app.core.security import generate_secure_token, hash_token
from app.merchant.models import Merchant, MerchantStaffMembership, StaffBranchAssignment
from app.merchant.staff_schemas import (
    StaffInvitationResponse,
    StaffInviteRequest,
    StaffResponse,
    StaffUpdateRequest,
)
from app.notification.providers import MockEmailProvider


class MerchantStaffService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.email_provider = MockEmailProvider()

    async def _owned_merchant(self, owner_id: uuid.UUID) -> Merchant:
        result = await self.session.execute(
            select(Merchant).where(
                Merchant.owner_user_id == owner_id, Merchant.deleted_at.is_(None)
            )
        )
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise ForbiddenError(
                message="A merchant owned by the current user is required.",
                error_code="MERCHANT_OWNERSHIP_REQUIRED",
            )
        return merchant

    @staticmethod
    def _staff_role(role: str) -> str:
        try:
            canonical = normalize_role(role)
        except ValueError as exc:
            raise UnprocessableEntityError(
                message=str(exc), error_code="INVALID_STAFF_ROLE"
            ) from exc
        if canonical not in STAFF_ROLES:
            raise UnprocessableEntityError(
                message="Staff role must be KitchenStaff or BranchManager.",
                error_code="INVALID_STAFF_ROLE",
            )
        return canonical

    async def _validate_branches(
        self, merchant_id: uuid.UUID, branch_ids: list[uuid.UUID]
    ) -> None:
        if not branch_ids:
            return
        count = await self.session.scalar(
            select(func.count(Branch.id))
            .join(Brand, Brand.id == Branch.brand_id)
            .where(
                Branch.id.in_(set(branch_ids)),
                Brand.merchant_id == merchant_id,
                Branch.deleted_at.is_(None),
            )
        )
        if count != len(set(branch_ids)):
            raise UnprocessableEntityError(
                message="One or more branches are outside this merchant.",
                error_code="BRANCH_SCOPE_INVALID",
            )

    async def list_staff(self, owner_id: uuid.UUID) -> list[StaffResponse]:
        merchant = await self._owned_merchant(owner_id)
        result = await self.session.execute(
            select(MerchantStaffMembership, User)
            .join(User, User.id == MerchantStaffMembership.user_id)
            .where(MerchantStaffMembership.merchant_id == merchant.id)
            .order_by(MerchantStaffMembership.created_at.desc())
        )
        responses = []
        for membership, user in result.all():
            assignments = await self.session.scalars(
                select(StaffBranchAssignment.branch_id).where(
                    StaffBranchAssignment.membership_id == membership.id
                )
            )
            responses.append(
                StaffResponse(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    role=membership.role,
                    is_active=membership.is_active,
                    branch_ids=list(assignments),
                    created_at=membership.created_at,
                )
            )
        return responses

    async def invite(
        self, owner_id: uuid.UUID, req: StaffInviteRequest
    ) -> StaffInvitationResponse:
        merchant = await self._owned_merchant(owner_id)
        role = self._staff_role(req.role)
        await self._validate_branches(merchant.id, req.branch_ids)
        raw = generate_secure_token()
        invitation = Invitation(
            email=req.email.strip().lower(),
            role=role,
            invited_by_user_id=owner_id,
            merchant_id=merchant.id,
            branch_ids=[str(branch_id) for branch_id in req.branch_ids],
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=settings.INVITATION_EXPIRE_DAYS),
        )
        self.session.add(invitation)
        await self.email_provider.send_email(
            invitation.email,
            "Merchant staff invitation",
            f"Your invitation token is: {raw}",
        )
        await self.session.commit()
        return StaffInvitationResponse(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            branch_ids=invitation.branch_ids or [],
            expires_at=invitation.expires_at,
            preview_token=raw if settings.ENVIRONMENT.casefold() != "production" else None,
        )

    async def _membership(
        self, owner_id: uuid.UUID, membership_id: uuid.UUID
    ) -> tuple[Merchant, MerchantStaffMembership]:
        merchant = await self._owned_merchant(owner_id)
        result = await self.session.execute(
            select(MerchantStaffMembership).where(
                MerchantStaffMembership.id == membership_id,
                MerchantStaffMembership.merchant_id == merchant.id,
            )
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise EntityNotFoundError(
                message="Staff membership not found.",
                error_code="STAFF_MEMBERSHIP_NOT_FOUND",
            )
        return merchant, membership

    async def update_staff(
        self, owner_id: uuid.UUID, membership_id: uuid.UUID, req: StaffUpdateRequest
    ) -> StaffResponse:
        merchant, membership = await self._membership(owner_id, membership_id)
        if req.role is not None:
            membership.role = self._staff_role(req.role)
            user = await self.session.get(User, membership.user_id)
            if user:
                user.role = membership.role
        if req.is_active is not None:
            membership.is_active = req.is_active
        if req.branch_ids is not None:
            await self._validate_branches(merchant.id, req.branch_ids)
            await self.session.execute(
                delete(StaffBranchAssignment).where(
                    StaffBranchAssignment.membership_id == membership.id
                )
            )
            self.session.add_all(
                [
                    StaffBranchAssignment(
                        membership_id=membership.id, branch_id=branch_id
                    )
                    for branch_id in set(req.branch_ids)
                ]
            )
        await self.session.commit()
        user = await self.session.get(User, membership.user_id)
        assignments = await self.session.scalars(
            select(StaffBranchAssignment.branch_id).where(
                StaffBranchAssignment.membership_id == membership.id
            )
        )
        return StaffResponse(
            id=membership.id,
            user_id=membership.user_id,
            email=user.email if user else "",
            role=membership.role,
            is_active=membership.is_active,
            branch_ids=list(assignments),
            created_at=membership.created_at,
        )

    async def remove_staff(
        self, owner_id: uuid.UUID, membership_id: uuid.UUID
    ) -> None:
        _, membership = await self._membership(owner_id, membership_id)
        await self.session.execute(
            delete(StaffBranchAssignment).where(
                StaffBranchAssignment.membership_id == membership.id
            )
        )
        await self.session.delete(membership)
        await self.session.commit()
