import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthActionToken, AuthSession, User
from app.auth.repository import UserRepositoryInterface
from app.auth.schemas import (
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.exceptions import (
    ConflictError,
    EntityNotFoundError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.config import settings
from app.core.roles import Role
from app.core.uuidv7 import uuid7
from app.notification.providers import MockEmailProvider


class AuthServiceInterface(ABC):
    """Abstract Service Interface for Auth Module."""

    @abstractmethod
    async def register_user(self, req: UserRegisterRequest) -> TokenResponse:
        pass

    @abstractmethod
    async def authenticate_user(self, req: UserLoginRequest) -> TokenResponse:
        pass

    @abstractmethod
    async def refresh_tokens(self, req: TokenRefreshRequest) -> TokenResponse:
        pass

    @abstractmethod
    async def get_current_user_profile(self, user_id: str) -> UserResponse:
        pass


class AuthService(AuthServiceInterface):
    """AuthService Application Layer implementation."""

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepositoryInterface,
    ):
        self.session = session
        self.user_repo = user_repo
        self.email_provider = MockEmailProvider()

    @staticmethod
    def _user_response(user: User) -> UserResponse:
        return UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def _issue_tokens(self, user: User) -> TokenResponse:
        session_id = uuid7()
        refresh_token = create_refresh_token(
            subject=str(user.id), session_id=str(session_id)
        )
        self.session.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=hash_token(refresh_token),
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        await self.session.flush()
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
            extra_claims={"email": user.email},
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=self._user_response(user),
        )

    async def _create_action_token(
        self, user: User, purpose: str, lifetime: timedelta
    ) -> str:
        from app.core.security import generate_secure_token

        raw_token = generate_secure_token()
        self.session.add(
            AuthActionToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_token(raw_token),
                expires_at=datetime.now(UTC) + lifetime,
            )
        )
        await self.session.flush()
        return raw_token

    async def register_user(self, req: UserRegisterRequest) -> TokenResponse:
        if req.role not in (None, "", Role.CUSTOMER.value):
            raise ForbiddenError(
                message="Public registration only creates Customer accounts.",
                error_code="PRIVILEGED_ROLE_REGISTRATION_FORBIDDEN",
            )
        # Domain Invariant INV-AUTH-001: Unique case-insensitive email
        existing_user = await self.user_repo.get_by_email(req.email)
        if existing_user:
            raise ConflictError(
                message="User with this email already exists.",
                error_code="EMAIL_ALREADY_EXISTS",
            )

        # Domain Invariant INV-AUTH-002: Password hashed using Argon2id
        hashed_pwd = hash_password(req.password)

        user = User(
            email=req.email.strip().lower(),
            password_hash=hashed_pwd,
            role=Role.CUSTOMER.value,
            is_active=True,
            is_verified=False,
        )

        created_user = await self.user_repo.create(user)

        verification_token = await self._create_action_token(
            created_user,
            "email_verification",
            timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
        )
        response = await self._issue_tokens(created_user)
        await self.email_provider.send_email(
            created_user.email,
            "Verify your email",
            f"Your verification token is: {verification_token}",
        )
        await self.session.commit()
        return response

    async def authenticate_user(self, req: UserLoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_email(req.email)
        if not user or not verify_password(req.password, user.password_hash or ""):
            raise UnauthorizedError(
                message="Invalid email or password.",
                error_code="INVALID_CREDENTIALS",
            )

        if not user.is_active:
            raise UnauthorizedError(
                message="User account is deactivated or suspended.",
                error_code="USER_INACTIVE",
            )

        response = await self._issue_tokens(user)
        await self.session.commit()
        return response

    async def refresh_tokens(self, req: TokenRefreshRequest) -> TokenResponse:
        try:
            payload = decode_token(req.refresh_token)
        except ValueError:
            raise UnauthorizedError(
                message="Invalid or expired refresh token.",
                error_code="INVALID_REFRESH_TOKEN",
            )

        if payload.get("type") != "refresh":
            raise UnauthorizedError(
                message="Provided token is not a valid refresh token.",
                error_code="INVALID_TOKEN_TYPE",
            )

        user_id_str = payload.get("sub")
        session_id_str = payload.get("sid")
        if not user_id_str or not session_id_str:
            raise UnauthorizedError(
                message="Invalid token subject.",
                error_code="INVALID_REFRESH_TOKEN",
            )

        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            raise UnauthorizedError(
                message="Invalid user ID format in token.",
                error_code="INVALID_REFRESH_TOKEN",
            )

        try:
            session_id = uuid.UUID(session_id_str)
        except ValueError:
            raise UnauthorizedError(
                message="Invalid refresh session.",
                error_code="INVALID_REFRESH_TOKEN",
            )

        session_result = await self.session.execute(
            select(AuthSession).where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_uuid,
                AuthSession.refresh_token_hash == hash_token(req.refresh_token),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        auth_session = session_result.scalar_one_or_none()
        if not auth_session:
            raise UnauthorizedError(
                message="Refresh token has been revoked, rotated, or expired.",
                error_code="INVALID_REFRESH_TOKEN",
            )

        user = await self.user_repo.get_by_id(user_uuid)
        if not user or not user.is_active:
            raise UnauthorizedError(
                message="User account not found or inactive.",
                error_code="USER_INACTIVE",
            )

        auth_session.revoked_at = datetime.now(UTC)
        auth_session.last_used_at = datetime.now(UTC)
        response = await self._issue_tokens(user)
        new_payload = decode_token(response.refresh_token)
        auth_session.replaced_by_session_id = uuid.UUID(new_payload["sid"])
        await self.session.commit()
        return response

    async def get_current_user_profile(self, user_id: str) -> UserResponse:
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise EntityNotFoundError(
                message="User not found.",
                error_code="USER_NOT_FOUND",
            )

        user = await self.user_repo.get_by_id(user_uuid)
        if not user:
            raise EntityNotFoundError(
                message="User not found.",
                error_code="USER_NOT_FOUND",
            )

        return UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
