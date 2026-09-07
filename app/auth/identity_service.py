import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthActionToken, AuthSession, Invitation, User
from app.auth.repository import UserRepository
from app.auth.schemas import MessageResponse, TokenResponse
from app.auth.service import AuthService
from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError, UnprocessableEntityError
from app.core.security import decode_token, generate_secure_token, hash_password, hash_token, verify_password
from app.merchant.models import MerchantStaffMembership, StaffBranchAssignment
from app.notification.providers import MockEmailProvider, NotificationProviderInterface


class IdentityService:
    def __init__(
        self,
        session: AsyncSession,
        email_provider: NotificationProviderInterface | None = None,
    ):
        self.session = session
        self.users = UserRepository(session)
        self.auth = AuthService(session, self.users)
        self.email_provider = email_provider or MockEmailProvider()

    @staticmethod
    def _preview(token: str) -> str | None:
        return token if settings.ENVIRONMENT.casefold() != "production" else None

    async def _new_action_token(
        self, user: User, purpose: str, lifetime: timedelta
    ) -> str:
        await self.session.execute(
            update(AuthActionToken)
            .where(
                AuthActionToken.user_id == user.id,
                AuthActionToken.purpose == purpose,
                AuthActionToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        raw = generate_secure_token()
        self.session.add(
            AuthActionToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + lifetime,
            )
        )
        await self.session.flush()
        return raw

    async def _consume_action_token(self, raw: str, purpose: str) -> tuple[AuthActionToken, User]:
        result = await self.session.execute(
            select(AuthActionToken, User)
            .join(User, User.id == AuthActionToken.user_id)
            .where(
                AuthActionToken.token_hash == hash_token(raw),
                AuthActionToken.purpose == purpose,
                AuthActionToken.used_at.is_(None),
                AuthActionToken.expires_at > datetime.now(UTC),
            )
        )
        row = result.one_or_none()
        if not row:
            raise UnprocessableEntityError(
                message="Token is invalid, expired, or already used.",
                error_code="INVALID_OR_EXPIRED_TOKEN",
            )
        token, user = row
        token.used_at = datetime.now(UTC)
        return token, user

    async def verify_email(self, token: str) -> MessageResponse:
        _, user = await self._consume_action_token(token, "email_verification")
        user.is_verified = True
        await self.session.commit()
        return MessageResponse(message="Email verified.")

    async def resend_verification(self, email: str) -> MessageResponse:
        user = await self.users.get_by_email(email)
        preview = None
        if user and user.is_active and not user.is_verified:
            token = await self._new_action_token(
                user,
                "email_verification",
                timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
            )
            await self.email_provider.send_email(
                user.email, "Verify your email", f"Your verification token is: {token}"
            )
            preview = self._preview(token)
            await self.session.commit()
        return MessageResponse(
            message="If the account exists and is unverified, a verification email was sent.",
            preview_token=preview,
        )

    async def forgot_password(self, email: str) -> MessageResponse:
        user = await self.users.get_by_email(email)
        preview = None
        if user and user.is_active:
            token = await self._new_action_token(
                user,
                "password_reset",
                timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
            )
            await self.email_provider.send_email(
                user.email, "Reset your password", f"Your password reset token is: {token}"
            )
            preview = self._preview(token)
            await self.session.commit()
        return MessageResponse(
            message="If the account exists, a password reset email was sent.",
            preview_token=preview,
        )

    async def reset_password(self, token: str, password: str) -> MessageResponse:
        _, user = await self._consume_action_token(token, "password_reset")
        user.password_hash = hash_password(password)
        await self._revoke_all(user.id)
        await self.session.commit()
        return MessageResponse(message="Password reset successfully.")

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> MessageResponse:
        user = await self.users.get_by_id(uuid.UUID(user_id))
        if not user or not verify_password(current_password, user.password_hash or ""):
            raise UnauthorizedError(
                message="Current password is incorrect.",
                error_code="INVALID_CURRENT_PASSWORD",
            )
        user.password_hash = hash_password(new_password)
        await self._revoke_all(user.id)
        await self.session.commit()
        return MessageResponse(message="Password changed. All sessions were revoked.")

    async def logout(self, refresh_token: str) -> MessageResponse:
        try:
            payload = decode_token(refresh_token)
            session_id = uuid.UUID(payload["sid"])
        except (ValueError, KeyError):
            raise UnauthorizedError(
                message="Invalid refresh token.", error_code="INVALID_REFRESH_TOKEN"
            )
        result = await self.session.execute(
            select(AuthSession).where(
                AuthSession.id == session_id,
                AuthSession.refresh_token_hash == hash_token(refresh_token),
            )
        )
        auth_session = result.scalar_one_or_none()
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(UTC)
            await self.session.commit()
        return MessageResponse(message="Logged out.")

    async def _revoke_all(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def logout_all(self, user_id: str) -> MessageResponse:
        await self._revoke_all(uuid.UUID(user_id))
        await self.session.commit()
        return MessageResponse(message="All sessions revoked.")

    async def accept_invitation(self, token: str, password: str) -> TokenResponse:
        result = await self.session.execute(
            select(Invitation).where(
                Invitation.token_hash == hash_token(token),
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.expires_at > datetime.now(UTC),
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise UnprocessableEntityError(
                message="Invitation is invalid, expired, or already used.",
                error_code="INVALID_OR_EXPIRED_INVITATION",
            )

        user = await self.users.get_by_email(invitation.email)
        if user and user.password_hash and not verify_password(password, user.password_hash):
            raise ConflictError(
                message="An account already exists; provide its current password.",
                error_code="INVITATION_ACCOUNT_EXISTS",
            )
        if not user:
            user = await self.users.create(
                User(
                    email=invitation.email,
                    password_hash=hash_password(password),
                    role=invitation.role,
                    is_active=True,
                    is_verified=True,
                )
            )
        else:
            user.role = invitation.role
            user.is_active = True
            user.is_verified = True

        if invitation.merchant_id:
            membership_result = await self.session.execute(
                select(MerchantStaffMembership).where(
                    MerchantStaffMembership.merchant_id == invitation.merchant_id,
                    MerchantStaffMembership.user_id == user.id,
                )
            )
            membership = membership_result.scalar_one_or_none()
            if not membership:
                membership = MerchantStaffMembership(
                    merchant_id=invitation.merchant_id,
                    user_id=user.id,
                    role=invitation.role,
                    is_active=True,
                )
                self.session.add(membership)
                await self.session.flush()
            else:
                membership.role = invitation.role
                membership.is_active = True
                await self.session.execute(
                    delete(StaffBranchAssignment).where(
                        StaffBranchAssignment.membership_id == membership.id
                    )
                )
            for branch_id in invitation.branch_ids or []:
                self.session.add(
                    StaffBranchAssignment(
                        membership_id=membership.id, branch_id=uuid.UUID(branch_id)
                    )
                )

        invitation.accepted_at = datetime.now(UTC)
        response = await self.auth._issue_tokens(user)
        await self.session.commit()
        return response
