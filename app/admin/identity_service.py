import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.identity_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    InvitationCreate,
    InvitationResponse,
    SessionResponse,
)
from app.auth.models import AuthSession, Invitation, User
from app.auth.repository import UserRepository
from app.auth.schemas import UserResponse
from app.core.config import settings
from app.core.exceptions import ConflictError, EntityNotFoundError, UnprocessableEntityError
from app.core.roles import STAFF_ROLES, normalize_role
from app.core.security import generate_secure_token, hash_password, hash_token
from app.branch.models import Branch
from app.brand.models import Brand
from app.notification.providers import MockEmailProvider


class AdminIdentityService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.email_provider = MockEmailProvider()

    @staticmethod
    def _response(user: User) -> UserResponse:
        return UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def list_users(self, skip: int, limit: int) -> list[UserResponse]:
        result = await self.session.execute(
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._response(user) for user in result.scalars()]

    async def create_user(self, req: AdminUserCreate) -> UserResponse:
        if await self.users.get_by_email(req.email):
            raise ConflictError(
                message="User with this email already exists.",
                error_code="EMAIL_ALREADY_EXISTS",
            )
        try:
            role = normalize_role(req.role)
        except ValueError as exc:
            raise UnprocessableEntityError(
                message=str(exc), error_code="INVALID_ROLE"
            ) from exc
        user = await self.users.create(
            User(
                email=req.email.strip().lower(),
                password_hash=hash_password(req.password),
                role=role,
                is_active=True,
                is_verified=req.is_verified,
            )
        )
        await self.session.commit()
        return self._response(user)

    async def update_user(
        self, user_id: uuid.UUID, req: AdminUserUpdate
    ) -> UserResponse:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(message="User not found.", error_code="USER_NOT_FOUND")
        if req.email is not None and req.email.casefold() != user.email.casefold():
            if await self.users.get_by_email(req.email):
                raise ConflictError(
                    message="User with this email already exists.",
                    error_code="EMAIL_ALREADY_EXISTS",
                )
            user.email = req.email.strip().lower()
        if req.role is not None:
            try:
                user.role = normalize_role(req.role)
            except ValueError as exc:
                raise UnprocessableEntityError(
                    message=str(exc), error_code="INVALID_ROLE"
                ) from exc
        if req.is_active is not None:
            user.is_active = req.is_active
            if not user.is_active:
                await self.revoke_sessions(user.id, commit=False)
        if req.is_verified is not None:
            user.is_verified = req.is_verified
        await self.session.commit()
        return self._response(user)

    async def list_sessions(self, user_id: uuid.UUID) -> list[SessionResponse]:
        if not await self.users.get_by_id(user_id):
            raise EntityNotFoundError(message="User not found.", error_code="USER_NOT_FOUND")
        result = await self.session.execute(
            select(AuthSession)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.created_at.desc())
        )
        return [
            SessionResponse(
                id=item.id,
                created_at=item.created_at,
                expires_at=item.expires_at,
                last_used_at=item.last_used_at,
                revoked_at=item.revoked_at,
            )
            for item in result.scalars()
        ]

    async def revoke_sessions(self, user_id: uuid.UUID, commit: bool = True) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        if commit:
            await self.session.commit()

    async def create_invitation(
        self, inviter_id: uuid.UUID, req: InvitationCreate
    ) -> InvitationResponse:
        try:
            role = normalize_role(req.role)
        except ValueError as exc:
            raise UnprocessableEntityError(
                message=str(exc), error_code="INVALID_ROLE"
            ) from exc
        if role in STAFF_ROLES and not req.merchant_id:
            raise UnprocessableEntityError(
                message="Staff invitations require a merchant.",
                error_code="MERCHANT_REQUIRED",
            )
        if req.branch_ids:
            if not req.merchant_id:
                raise UnprocessableEntityError(
                    message="Branch assignments require a merchant.",
                    error_code="MERCHANT_REQUIRED",
                )
            count = await self.session.scalar(
                select(func.count(Branch.id))
                .join(Brand, Brand.id == Branch.brand_id)
                .where(
                    Branch.id.in_(req.branch_ids),
                    Brand.merchant_id == req.merchant_id,
                    Branch.deleted_at.is_(None),
                )
            )
            if count != len(set(req.branch_ids)):
                raise UnprocessableEntityError(
                    message="One or more branches do not belong to the merchant.",
                    error_code="BRANCH_SCOPE_INVALID",
                )
        raw = generate_secure_token()
        invitation = Invitation(
            email=req.email.strip().lower(),
            role=role,
            invited_by_user_id=inviter_id,
            merchant_id=req.merchant_id,
            branch_ids=[str(branch_id) for branch_id in req.branch_ids],
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=settings.INVITATION_EXPIRE_DAYS),
        )
        self.session.add(invitation)
        await self.email_provider.send_email(
            invitation.email,
            "You are invited",
            f"Your invitation token is: {raw}",
        )
        await self.session.commit()
        return InvitationResponse(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            merchant_id=invitation.merchant_id,
            branch_ids=invitation.branch_ids or [],
            expires_at=invitation.expires_at,
            preview_token=raw if settings.ENVIRONMENT.casefold() != "production" else None,
        )
