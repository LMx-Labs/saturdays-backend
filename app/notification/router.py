import json
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.config import settings
from app.core.database import get_db_session
from app.notification.providers import MockEmailProvider, NotificationProviderInterface
from app.notification.repository import (
    NotificationRepository,
    NotificationRepositoryInterface,
)
from app.notification.schemas import NotificationResponse, NotificationSendRequest
from app.notification.service import NotificationService, NotificationServiceInterface
from app.notification.whatsapp import build_whatsapp_provider
from app.notification.whatsapp_webhook import process_webhook, signature_is_valid

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


@router.get(
    "/whatsapp/webhook",
    response_class=PlainTextResponse,
    summary="WhatsApp webhook verification",
    description="Meta calls this once, when the webhook is registered, to check we own it.",
)
async def whatsapp_webhook_verify(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if mode == "subscribe" and expected and token == expected and challenge is not None:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post(
    "/whatsapp/webhook",
    status_code=status.HTTP_200_OK,
    summary="WhatsApp delivery reports and replies",
    description="Receives message delivery reports and customer replies (STOP). Signed by Meta.",
)
async def whatsapp_webhook_receive(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    raw_body = await request.body()
    # Without a valid signature this is anyone on the internet, not WhatsApp: refuse.
    if not signature_is_valid(
        raw_body, x_hub_signature_256, settings.WHATSAPP_APP_SECRET
    ):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = json.loads(raw_body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    return {"status": "ok", **await process_webhook(session, payload)}


@router.get(
    "/whatsapp/status",
    summary="Is WhatsApp order updates live?",
    description=(
        "Public yes/no so the app only offers the WhatsApp tick-box when messages will really "
        "be sent. Reveals nothing else about the configuration."
    ),
)
async def whatsapp_status() -> dict[str, bool]:
    live = (
        settings.WHATSAPP_ENABLED
        and build_whatsapp_provider(settings) is not None
        and bool(settings.WHATSAPP_TEMPLATE_ORDER_CONFIRMED.strip())
    )
    return {"enabled": live}
