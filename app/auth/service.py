import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepositoryInterface
from app.auth.schemas import (
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.exceptions import ConflictError, EntityNotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


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

    @staticmethod
    def _access_claims(user: User) -> dict[str, str]:
        claims = {"email": user.email}
        if user.branch_id is not None:
            claims["branch_id"] = str(user.branch_id)
        return claims

    @staticmethod
    def _to_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            branch_id=str(user.branch_id) if user.branch_id else None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def register_user(self, req: UserRegisterRequest) -> TokenResponse:
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
            role=req.role,
            is_active=True,
            is_verified=False,
        )

        created_user = await self.user_repo.create(user)

        # Transaction Scope: Commit write operation
        await self.session.commit()

        # Domain Invariant INV-AUTH-003: 15-min Access Token, 7-day Refresh Token
        access_token = create_access_token(
            subject=str(created_user.id),
            role=created_user.role,
            extra_claims=self._access_claims(created_user),
        )
        refresh_token = create_refresh_token(subject=str(created_user.id))

        user_resp = self._to_user_response(created_user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=900,
            user=user_resp,
        )

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

        access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
            extra_claims=self._access_claims(user),
        )
        refresh_token = create_refresh_token(subject=str(user.id))

        user_resp = self._to_user_response(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=900,
            user=user_resp,
        )

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
        if not user_id_str:
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

        user = await self.user_repo.get_by_id(user_uuid)
        if not user or not user.is_active:
            raise UnauthorizedError(
                message="User account not found or inactive.",
                error_code="USER_INACTIVE",
            )

        access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
            extra_claims=self._access_claims(user),
        )
        new_refresh_token = create_refresh_token(subject=str(user.id))

        user_resp = self._to_user_response(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=900,
            user=user_resp,
        )

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

        return self._to_user_response(user)
