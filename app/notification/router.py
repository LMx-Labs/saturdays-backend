import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.notification.providers import MockEmailProvider, NotificationProviderInterface
from app.notification.repository import (
    NotificationRepository,
    NotificationRepositoryInterface,
)
from app.notification.schemas import NotificationResponse, NotificationSendRequest
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
    return NotificationService(
        session=session, notif_repo=notif_repo, provider=provider
    )


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
    return await notif_service.get_user_notifications(
        user_id=uuid.UUID(current_user.sub)
    )


@router.post(
    "/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send transactional notification via background task",
)
async def send_notification(
    req: NotificationSendRequest,
    background_tasks: BackgroundTasks,
    current_user: UserClaims = Depends(get_current_user),
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
