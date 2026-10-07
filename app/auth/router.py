from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import UserRepository, UserRepositoryInterface
from app.auth.schemas import (
    TokenRefreshRequest,
    TokenResponse,
    UserClaims,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.auth.service import AuthService, AuthServiceInterface
from app.core.database import get_db_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepositoryInterface:
    return UserRepository(session=session)


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> AuthServiceInterface:
    return AuthService(
        session=session,
        user_repo=user_repo,
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserClaims:
    """Dependency for extracting and validating JWT bearer tokens."""
    try:
        payload = decode_token(token)
    except ValueError:
        raise UnauthorizedError(
            message="Invalid or expired access token.",
            error_code="INVALID_ACCESS_TOKEN",
        )

    if payload.get("type") != "access":
        raise UnauthorizedError(
            message="Token provided is not an access token.",
            error_code="INVALID_TOKEN_TYPE",
        )

    sub = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email", "")

    if not sub or not role:
        raise UnauthorizedError(
            message="Malformed token payload.",
            error_code="INVALID_ACCESS_TOKEN",
        )

    return UserClaims(
        sub=sub, email=email, role=role, branch_id=payload.get("branch_id")
    )


def require_role(allowed_roles: list[str]):
    """RBAC Role check dependency factory."""

    def role_checker(
        current_user: UserClaims = Depends(get_current_user),
    ) -> UserClaims:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                message=f"Access denied for role '{current_user.role}'.",
                error_code="ROLE_NOT_AUTHORIZED",
            )
        return current_user

    return role_checker


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user, hashes password with Argon2id, creates users row, and returns JWT tokens.",
)
async def register(
    req: UserRegisterRequest,
    auth_service: AuthServiceInterface = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.register_user(req)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticates credentials against Argon2id hash and issues 15-min access token + 7-day refresh token.",
)
async def login(
    req: UserLoginRequest,
    auth_service: AuthServiceInterface = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.authenticate_user(req)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Validates 7-day refresh token and issues fresh access and refresh token pair.",
)
async def refresh(
    req: TokenRefreshRequest,
    auth_service: AuthServiceInterface = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.refresh_tokens(req)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns authenticated user profile details from validated JWT claims.",
)
async def me(
    current_user: UserClaims = Depends(get_current_user),
    auth_service: AuthServiceInterface = Depends(get_auth_service),
) -> UserResponse:
    return await auth_service.get_current_user_profile(current_user.sub)
