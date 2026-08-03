import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainInvariantError, EntityNotFoundError
from app.menu.models import MenuCategory, MenuItem
from app.order.models import Order, OrderItem
from app.order.repository import OrderRepositoryInterface
from app.order.schemas import OrderCreateRequest
from app.order.websocket_manager import ws_manager

logger = structlog.get_logger()


class OrderServiceInterface(ABC):
    @abstractmethod
    async def create_order(
        self,
        user_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        req: OrderCreateRequest,
    ) -> Order:
        pass

    @abstractmethod
    async def update_order_status(
        self,
        order_id: uuid.UUID,
        changed_by_user_id: uuid.UUID,
        target_status: str,
    ) -> Order:
        pass

    @abstractmethod
    async def cancel_order(
        self,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Order:
        pass

    @abstractmethod
    async def get_order(self, order_id: uuid.UUID) -> Order:
        pass

    @abstractmethod
    async def get_customer_orders(self, customer_profile_id: uuid.UUID) -> Sequence[Order]:
        pass

    @abstractmethod
    async def get_branch_orders(
        self, branch_id: uuid.UUID, status: str | None = None
    ) -> Sequence[Order]:
        pass


class OrderService(OrderServiceInterface):
    VALID_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "PLACED": {"ACCEPTED", "CANCELLED"},
        "ACCEPTED": {"PREPARING", "CANCELLED"},
        "PREPARING": {"READY"},
        "READY": {"COMPLETED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    }

    def __init__(self, session: AsyncSession, order_repo: OrderRepositoryInterface):
        self.session = session
        self.order_repo = order_repo

    async def create_order(
        self,
        user_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        req: OrderCreateRequest,
    ) -> Order:
        total_amount = 0.0
        order_items: list[OrderItem] = []

        for item_req in req.items:
            # Fetch menu item details for snapshot and branch invariant check
            stmt = (
                select(MenuItem)
                .where(
                    MenuItem.id == item_req.menu_item_id,
                    MenuItem.deleted_at.is_(None),
                )
                .options(selectinload(MenuItem.category).selectinload(MenuCategory.menu))
            )
            res = await self.session.execute(stmt)
            menu_item = res.scalars().first()

            if not menu_item:
                raise EntityNotFoundError(
                    message=f"Menu item '{item_req.menu_item_id}' not found.",
                    error_code="MENU_ITEM_NOT_FOUND",
                )

            # INV-0001: Single Branch Ownership check
            if (
                menu_item.category is not None
                and menu_item.category.menu is not None
                and menu_item.category.menu.branch_id != req.branch_id
            ):
                raise DomainInvariantError(
                    message=f"Menu item '{menu_item.id}' does not belong to branch '{req.branch_id}'.",
                    error_code="CROSS_BRANCH_ORDER_VIOLATION",
                )

            unit_price = float(menu_item.base_price)
            item_total = unit_price * item_req.quantity
            total_amount += item_total

            order_item = OrderItem(
                menu_item_id=menu_item.id,
                item_name_snapshot=menu_item.name,
                unit_price_snapshot=unit_price,
                quantity=item_req.quantity,
                selected_modifiers_snapshot=item_req.selected_modifiers_snapshot,
            )
            order_items.append(order_item)

        order = Order(
            customer_profile_id=customer_profile_id,
            branch_id=req.branch_id,
            total_amount=round(total_amount, 2),
            status="PLACED",
            delivery_address_snapshot=req.delivery_address_snapshot,
        )

        created_order = await self.order_repo.create_order(
            order=order,
            items=order_items,
            user_id=user_id,
        )
        await self.session.commit()
        refreshed_order = await self.get_order(created_order.id)

        # Publish OrderPlacedEvent
        logger.info(
            "OrderPlacedEvent",
            order_id=str(refreshed_order.id),
            branch_id=str(refreshed_order.branch_id),
            customer_profile_id=str(refreshed_order.customer_profile_id),
            total_amount=float(refreshed_order.total_amount),
        )

        # Real-time WebSocket broadcast to kitchen terminals (ADR-0010)
        await ws_manager.broadcast_to_branch(
            branch_id=refreshed_order.branch_id,
            message={
                "event": "ORDER_PLACED",
                "order_id": str(refreshed_order.id),
                "total_amount": float(refreshed_order.total_amount),
                "status": refreshed_order.status,
            },
        )

        return refreshed_order

    async def update_order_status(
        self,
        order_id: uuid.UUID,
        changed_by_user_id: uuid.UUID,
        target_status: str,
    ) -> Order:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise EntityNotFoundError(
                message=f"Order '{order_id}' not found.",
                error_code="ORDER_NOT_FOUND",
            )

        current_status = order.status
        allowed_targets = self.VALID_TRANSITIONS.get(current_status, set())

        # INV-ORD-002: Valid State Machine Transition
        if target_status not in allowed_targets:
            raise DomainInvariantError(
                message=f"Illegal order status transition from '{current_status}' to '{target_status}'.",
                error_code="ILLEGAL_STATUS_TRANSITION",
            )

        updated_order = await self.order_repo.update_order_status(
            order_id=order_id,
            new_status=target_status,
            changed_by_user_id=changed_by_user_id,
        )
        await self.session.commit()
        refreshed_order = await self.get_order(updated_order.id)

        if target_status == "ACCEPTED":
            logger.info(
                "OrderAcceptedEvent",
                order_id=str(refreshed_order.id),
                branch_id=str(refreshed_order.branch_id),
            )

        # Real-time WebSocket broadcast
        await ws_manager.broadcast_to_branch(
            branch_id=refreshed_order.branch_id,
            message={
                "event": "ORDER_STATUS_CHANGED",
                "order_id": str(refreshed_order.id),
                "previous_status": current_status,
                "status": target_status,
            },
        )

        return refreshed_order

    async def cancel_order(
        self,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> Order:
        return await self.update_order_status(
            order_id=order_id,
            changed_by_user_id=user_id,
            target_status="CANCELLED",
        )

    async def get_order(self, order_id: uuid.UUID) -> Order:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise EntityNotFoundError(
                message=f"Order '{order_id}' not found.",
                error_code="ORDER_NOT_FOUND",
            )
        return order

    async def get_customer_orders(self, customer_profile_id: uuid.UUID) -> Sequence[Order]:
        return await self.order_repo.get_customer_orders(customer_profile_id)

    async def get_branch_orders(
        self, branch_id: uuid.UUID, status: str | None = None
    ) -> Sequence[Order]:
        return await self.order_repo.get_branch_orders(branch_id, status)
