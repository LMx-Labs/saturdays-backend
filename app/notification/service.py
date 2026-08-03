import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.models import Notification
from app.notification.providers import MockEmailProvider, NotificationProviderInterface
from app.notification.repository import NotificationRepositoryInterface
from app.notification.schemas import NotificationResponse


class NotificationServiceInterface(ABC):
    @abstractmethod
    async def send_email_notification(
        self, user_id: uuid.UUID, recipient: str, subject: str, body: str
    ) -> NotificationResponse:
        pass

    @abstractmethod
    async def send_order_placed_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, total_amount: float
    ) -> NotificationResponse:
        pass

    @abstractmethod
    async def send_order_status_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, new_status: str
    ) -> NotificationResponse:
        pass

    @abstractmethod
    async def send_payment_verified_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, amount: float
    ) -> NotificationResponse:
        pass

    @abstractmethod
    async def send_refund_processed_notification(
        self,
        user_id: uuid.UUID,
        recipient: str,
        order_number: str,
        refund_amount: float,
    ) -> NotificationResponse:
        pass

    @abstractmethod
    async def get_user_notifications(self, user_id: uuid.UUID) -> list[NotificationResponse]:
        pass


class NotificationService(NotificationServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        notif_repo: NotificationRepositoryInterface,
        provider: NotificationProviderInterface | None = None,
    ):
        self.session = session
        self.notif_repo = notif_repo
        self.provider = provider or MockEmailProvider()

    async def send_email_notification(
        self, user_id: uuid.UUID, recipient: str, subject: str, body: str
    ) -> NotificationResponse:
        # Create record in PENDING status
        notif = Notification(
            user_id=user_id,
            channel="EMAIL",
            recipient=recipient,
            subject=subject,
            body=body,
            status="PENDING",
        )
        created = await self.notif_repo.create_notification(notif)
        await self.session.commit()

        # Dispatch via decoupled vendor provider interface (INV-NOTIF-001)
        try:
            vendor_msg_id = await self.provider.send_email(recipient, subject, body)
            updated = await self.notif_repo.update_status(
                created.id, status="SENT", vendor_message_id=vendor_msg_id
            )
            await self.session.commit()
            return NotificationResponse.model_validate(updated or created)
        except Exception:  # noqa: BLE001
            updated = await self.notif_repo.update_status(created.id, status="FAILED")
            await self.session.commit()
            return NotificationResponse.model_validate(updated or created)

    async def send_order_placed_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, total_amount: float
    ) -> NotificationResponse:
        subject = f"Order #{order_number} Confirmed - Saturdays"
        body = (
            f"Thank you for your order! Your order #{order_number} for ₹{total_amount:.2f} "
            f"has been received and is being prepared."
        )
        return await self.send_email_notification(user_id, recipient, subject, body)

    async def send_order_status_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, new_status: str
    ) -> NotificationResponse:
        subject = f"Order #{order_number} Update: {new_status}"
        body = f"Your order #{order_number} status has been updated to: {new_status}."
        return await self.send_email_notification(user_id, recipient, subject, body)

    async def send_payment_verified_notification(
        self, user_id: uuid.UUID, recipient: str, order_number: str, amount: float
    ) -> NotificationResponse:
        subject = f"Payment Verified for Order #{order_number}"
        body = f"We have successfully received your payment of ₹{amount:.2f} for order #{order_number}."
        return await self.send_email_notification(user_id, recipient, subject, body)

    async def send_refund_processed_notification(
        self,
        user_id: uuid.UUID,
        recipient: str,
        order_number: str,
        refund_amount: float,
    ) -> NotificationResponse:
        subject = f"Refund Processed for Order #{order_number}"
        body = (
            f"A refund of ₹{refund_amount:.2f} has been processed for your order #{order_number}."
        )
        return await self.send_email_notification(user_id, recipient, subject, body)

    async def get_user_notifications(self, user_id: uuid.UUID) -> list[NotificationResponse]:
        notifications = await self.notif_repo.get_by_user_id(user_id)
        return [NotificationResponse.model_validate(n) for n in notifications]
