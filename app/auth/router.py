from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.identity_service import IdentityService
from app.auth.repository import UserRepository, UserRepositoryInterface
from app.auth.schemas import (
    EmailRequest,
    InvitationAcceptRequest,
    LogoutRequest,
    MessageResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    TokenRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserClaims,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.auth.service import AuthService, AuthServiceInterface
from app.core.authorization import get_current_user, require_role  # noqa: F401
from app.core.database import get_db_session

router = APIRouter(prefix="/auth", tags=["Auth"])


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


def get_identity_service(
    session: AsyncSession = Depends(get_db_session),
) -> IdentityService:
    return IdentityService(session)


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


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    req: TokenRequest,
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.verify_email(req.token)


@router.post("/verification/resend", response_model=MessageResponse)
async def resend_verification(
    req: EmailRequest,
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.resend_verification(req.email)


@router.post("/password/forgot", response_model=MessageResponse)
async def forgot_password(
    req: EmailRequest,
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.forgot_password(req.email)


@router.post("/password/reset", response_model=MessageResponse)
async def reset_password(
    req: PasswordResetRequest,
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.reset_password(req.token, req.new_password)


@router.post("/password/change", response_model=MessageResponse)
async def change_password(
    req: PasswordChangeRequest,
    current_user: UserClaims = Depends(get_current_user),
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.change_password(
        current_user.sub, req.current_password, req.new_password
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    req: LogoutRequest,
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.logout(req.refresh_token)


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: UserClaims = Depends(get_current_user),
    service: IdentityService = Depends(get_identity_service),
) -> MessageResponse:
    return await service.logout_all(current_user.sub)


@router.post(
    "/invitations/accept",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def accept_invitation(
    req: InvitationAcceptRequest,
    service: IdentityService = Depends(get_identity_service),
) -> TokenResponse:
    return await service.accept_invitation(req.token, req.password)
