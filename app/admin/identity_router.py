import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.identity_schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    InvitationCreate,
    InvitationResponse,
    SessionResponse,
)
from app.admin.identity_service import AdminIdentityService
from app.auth.schemas import MessageResponse, UserClaims, UserResponse
from app.core.authorization import require_role
from app.core.database import get_db_session
from app.core.roles import Role

router = APIRouter(prefix="/admin", tags=["Admin Identity"])


def get_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminIdentityService:
    return AdminIdentityService(session)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> list[UserResponse]:
    return await service.list_users(skip, limit)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: AdminUserCreate,
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> UserResponse:
    return await service.create_user(req)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    req: AdminUserUpdate,
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> UserResponse:
    return await service.update_user(user_id, req)


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> UserResponse:
    return await service.update_user(user_id, AdminUserUpdate(is_active=False))


@router.get("/users/{user_id}/sessions", response_model=list[SessionResponse])
async def list_user_sessions(
    user_id: uuid.UUID,
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> list[SessionResponse]:
    return await service.list_sessions(user_id)


@router.delete("/users/{user_id}/sessions", response_model=MessageResponse)
async def revoke_user_sessions(
    user_id: uuid.UUID,
    _current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> MessageResponse:
    await service.revoke_sessions(user_id)
    return MessageResponse(message="All user sessions revoked.")


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    req: InvitationCreate,
    current: UserClaims = Depends(require_role([Role.PLATFORM_ADMIN.value])),
    service: AdminIdentityService = Depends(get_service),
) -> InvitationResponse:
    return await service.create_invitation(uuid.UUID(current.sub), req)
