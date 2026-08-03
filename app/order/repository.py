import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundError
from app.order.models import Order, OrderItem, OrderStatusLog


class OrderRepositoryInterface(ABC):
    @abstractmethod
    async def create_order(
        self,
        order: Order,
        items: list[OrderItem],
        user_id: uuid.UUID,
    ) -> Order:
        pass

    @abstractmethod
    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        pass

    @abstractmethod
    async def get_by_id_for_update(self, order_id: uuid.UUID) -> Order | None:
        pass

    @abstractmethod
    async def get_customer_orders(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[Order]:
        pass

    @abstractmethod
    async def get_branch_orders(
        self, branch_id: uuid.UUID, status: str | None = None
    ) -> Sequence[Order]:
        pass

    @abstractmethod
    async def update_order_status(
        self, order_id: uuid.UUID, new_status: str, changed_by_user_id: uuid.UUID
    ) -> Order:
        pass


class OrderRepository(OrderRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_order(
        self,
        order: Order,
        items: list[OrderItem],
        user_id: uuid.UUID,
    ) -> Order:
        self.session.add(order)
        await self.session.flush()

        for item in items:
            item.order_id = order.id
            self.session.add(item)

        # Initial status log (INV-ORD-001)
        initial_log = OrderStatusLog(
            order_id=order.id,
            previous_status=None,
            new_status=order.status,
            changed_by_user_id=user_id,
        )
        self.session.add(initial_log)
        await self.session.flush()

        stmt = (
            select(Order)
            .where(Order.id == order.id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_logs),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one()

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_logs),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_id_for_update(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_logs),
            )
            .with_for_update()
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_customer_orders(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.customer_profile_id == customer_profile_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_logs),
            )
            .order_by(Order.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_branch_orders(
        self, branch_id: uuid.UUID, status: str | None = None
    ) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.branch_id == branch_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_logs),
            )
        )
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc())

        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def update_order_status(
        self, order_id: uuid.UUID, new_status: str, changed_by_user_id: uuid.UUID
    ) -> Order:
        order = await self.get_by_id_for_update(order_id)
        if not order:
            raise EntityNotFoundError(
                message=f"Order '{order_id}' not found.",
                error_code="ORDER_NOT_FOUND",
            )

        prev_status = order.status
        order.status = new_status
        log = OrderStatusLog(
            order_id=order.id,
            previous_status=prev_status,
            new_status=new_status,
            changed_by_user_id=changed_by_user_id,
        )
        self.session.add(log)
        await self.session.flush()
        return order
