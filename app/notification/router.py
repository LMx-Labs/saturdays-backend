import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.notification.providers import MockEmailProvider, NotificationProviderInterface
from app.notification.repository import (
    NotificationRepository,
    NotificationRepositoryInterface,
)
from app.notification.models import Notification, NotificationPreference
from app.notification.schemas import (
    NotificationPreferences,
    NotificationResponse,
    NotificationSendRequest,
)
from app.notification.service import NotificationService, NotificationServiceInterface

router = APIRouter(prefix="/notifications", tags=["Notification"])


def get_notification_repository(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationRepositoryInterface:
    return NotificationRepository(session=session)


def get_notification_provider() -> NotificationProviderInterface:
    return MockEmailProvider()


def get_notification_service(
    session: AsyncSession = Depends(get_db_session),
    notif_repo: NotificationRepositoryInterface = Depends(get_notification_repository),
    provider: NotificationProviderInterface = Depends(get_notification_provider),
) -> NotificationServiceInterface:
    return NotificationService(session=session, notif_repo=notif_repo, provider=provider)


@router.get(
    "/me",
    response_model=list[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user notification logs",
)
async def get_my_notifications(
    current_user: UserClaims = Depends(get_current_user),
    notif_service: NotificationServiceInterface = Depends(get_notification_service),
) -> list[NotificationResponse]:
    return await notif_service.get_user_notifications(user_id=uuid.UUID(current_user.sub))


@router.post(
    "/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send transactional notification via background task",
)
async def send_notification(
    req: NotificationSendRequest,
    background_tasks: BackgroundTasks,
    current_user: UserClaims = Depends(require_role(["PlatformAdmin"])),
    notif_service: NotificationServiceInterface = Depends(get_notification_service),
) -> NotificationResponse:
    user_id = uuid.UUID(current_user.sub)
    # Trigger dispatch immediately
    res = await notif_service.send_email_notification(
        user_id=user_id,
        recipient=req.recipient,
        subject=req.subject,
        body=req.body,
    )
    return res


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Notification:
    notification = await session.get(Notification, notification_id)
    if not notification or notification.user_id != uuid.UUID(current_user.sub):
        from app.core.exceptions import EntityNotFoundError

        raise EntityNotFoundError("Notification not found.", "NOTIFICATION_NOT_FOUND")
    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(notification)
    return notification


@router.patch("/me/read-all")
async def mark_all_notifications_read(
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == uuid.UUID(current_user.sub),
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await session.commit()
    return {"updated": result.rowcount or 0}


@router.get("/me/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationPreference:
    user_id = uuid.UUID(current_user.sub)
    preferences = await session.get(NotificationPreference, user_id)
    if not preferences:
        preferences = NotificationPreference(user_id=user_id)
        session.add(preferences)
        await session.commit()
        await session.refresh(preferences)
    return preferences


@router.put("/me/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    req: NotificationPreferences,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationPreference:
    user_id = uuid.UUID(current_user.sub)
    preferences = await session.get(NotificationPreference, user_id)
    if not preferences:
        preferences = NotificationPreference(user_id=user_id)
        session.add(preferences)
    for field, value in req.model_dump().items():
        setattr(preferences, field, value)
    await session.commit()
    await session.refresh(preferences)
    return preferences
