import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notification.models import Notification


class NotificationRepositoryInterface(ABC):
    @abstractmethod
    async def create_notification(self, notification: Notification) -> Notification:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> Sequence[Notification]:
        pass

    @abstractmethod
    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        pass

    @abstractmethod
    async def update_status(
        self,
        notification_id: uuid.UUID,
        status: str,
        vendor_message_id: str | None = None,
    ) -> Notification | None:
        pass


class NotificationRepository(NotificationRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def get_by_user_id(self, user_id: uuid.UUID) -> Sequence[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        stmt = select(Notification).where(Notification.id == notification_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_status(
        self,
        notification_id: uuid.UUID,
        status: str,
        vendor_message_id: str | None = None,
    ) -> Notification | None:
        notification = await self.get_by_id(notification_id)
        if notification:
            notification.status = status
            if vendor_message_id:
                notification.vendor_message_id = vendor_message_id
            await self.session.flush()
            await self.session.refresh(notification)
        return notification
