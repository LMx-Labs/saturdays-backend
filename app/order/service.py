import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cart.models import CartItem
from app.checkout.models import CheckoutQuote
from app.core.exceptions import DomainInvariantError, EntityNotFoundError
from app.coupon.models import Coupon, CouponRedemption
from app.inventory.models import InventoryItem, InventoryLog
from app.menu.models import MenuCategory, MenuItem
from app.order.models import Order, OrderItem, StockReservation
from app.order.events import OrderEventPublisher
from app.order.repository import OrderRepositoryInterface
from app.order.schemas import OrderCreateRequest

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
        if req.quote_id:
            return await self._create_order_from_quote(
                user_id=user_id,
                customer_profile_id=customer_profile_id,
                quote_id=req.quote_id,
            )
        return await self._create_legacy_server_priced_order(
            user_id=user_id,
            customer_profile_id=customer_profile_id,
            req=req,
        )

    async def _create_order_from_quote(
        self,
        user_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        quote_id: uuid.UUID,
    ) -> Order:
        quote = await self.session.scalar(
            select(CheckoutQuote).where(CheckoutQuote.id == quote_id).with_for_update()
        )
        if not quote:
            raise EntityNotFoundError("Checkout quote not found.", "QUOTE_NOT_FOUND")
        if quote.customer_profile_id != customer_profile_id:
            raise DomainInvariantError(
                "Checkout quote belongs to another customer.",
                "QUOTE_OWNERSHIP_MISMATCH",
            )
        if quote.consumed_at is not None:
            raise DomainInvariantError(
                "Checkout quote has already been consumed.", "QUOTE_ALREADY_CONSUMED"
            )
        expires_at = (
            quote.expires_at if quote.expires_at.tzinfo else quote.expires_at.replace(tzinfo=UTC)
        )
        if datetime.now(UTC) >= expires_at:
            raise DomainInvariantError("Checkout quote has expired.", "QUOTE_EXPIRED")
        if quote.coupon_id:
            coupon = await self.session.scalar(
                select(Coupon).where(Coupon.id == quote.coupon_id).with_for_update()
            )
            redemptions = await self.session.scalar(
                select(func.count(CouponRedemption.id)).where(
                    CouponRedemption.coupon_id == quote.coupon_id,
                    CouponRedemption.customer_profile_id == customer_profile_id,
                )
            )
            if not coupon or (redemptions or 0) >= coupon.max_redemptions_per_user:
                raise DomainInvariantError(
                    "Coupon redemption limit has been reached.",
                    "COUPON_USAGE_LIMIT_REACHED",
                )

        order = Order(
            customer_profile_id=customer_profile_id,
            branch_id=quote.branch_id,
            checkout_quote_id=quote.id,
            coupon_id=quote.coupon_id,
            subtotal=float(quote.subtotal),
            discount_amount=float(quote.discount_amount),
            tax_amount=float(quote.tax_amount),
            delivery_fee=float(quote.delivery_fee),
            total_amount=float(quote.final_amount),
            currency=quote.currency,
            status="PLACED",
            delivery_address_snapshot=quote.address_snapshot,
        )
        items = [
            OrderItem(
                menu_item_id=uuid.UUID(item["menu_item_id"]),
                item_name_snapshot=item["name"],
                unit_price_snapshot=float(item["unit_price"]),
                quantity=int(item["quantity"]),
                selected_modifiers_snapshot=item.get("selected_modifiers"),
            )
            for item in quote.items_snapshot
        ]
        created_order = await self.order_repo.create_order(order, items, user_id)

        for item in items:
            inventory = await self.session.scalar(
                select(InventoryItem)
                .where(
                    InventoryItem.branch_id == quote.branch_id,
                    InventoryItem.menu_item_id == item.menu_item_id,
                )
                .with_for_update()
            )
            if not inventory or not inventory.is_in_stock or inventory.quantity < item.quantity:
                raise DomainInvariantError(
                    f"Insufficient stock for '{item.item_name_snapshot}'.",
                    "INSUFFICIENT_STOCK",
                )
            previous = inventory.quantity
            inventory.quantity -= item.quantity
            inventory.is_in_stock = inventory.quantity > 0
            self.session.add(
                InventoryLog(
                    inventory_item_id=inventory.id,
                    change_amount=-item.quantity,
                    previous_quantity=previous,
                    new_quantity=inventory.quantity,
                    reason=f"ORDER_RESERVED:{created_order.id}",
                )
            )
            self.session.add(
                StockReservation(
                    order_id=created_order.id,
                    inventory_item_id=inventory.id,
                    quantity=item.quantity,
                )
            )

        if quote.coupon_id:
            self.session.add(
                CouponRedemption(
                    coupon_id=quote.coupon_id,
                    customer_profile_id=customer_profile_id,
                    order_id=created_order.id,
                    discount_amount_applied=float(quote.discount_amount),
                )
            )
        quote.consumed_at = datetime.now(UTC)
        quote.order_id = created_order.id
        await self.session.execute(delete(CartItem).where(CartItem.cart_id == quote.cart_id))
        await self.session.commit()
        return await self._publish_created_order(created_order.id)

    async def _create_legacy_server_priced_order(
        self,
        user_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        req: OrderCreateRequest,
    ) -> Order:
        if not req.branch_id or not req.items:
            raise DomainInvariantError(
                "A valid checkout quote is required.", "CHECKOUT_QUOTE_REQUIRED"
            )
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
            subtotal=round(total_amount, 2),
            discount_amount=0,
            tax_amount=0,
            delivery_fee=0,
            currency="INR",
            status="PLACED",
            delivery_address_snapshot=req.delivery_address_snapshot,
        )

        created_order = await self.order_repo.create_order(
            order=order,
            items=order_items,
            user_id=user_id,
        )
        await self.session.commit()
        return await self._publish_created_order(created_order.id)

    async def _publish_created_order(self, order_id: uuid.UUID) -> Order:
        refreshed_order = await self.get_order(order_id)
        logger.info(
            "OrderPlacedEvent",
            order_id=str(refreshed_order.id),
            branch_id=str(refreshed_order.branch_id),
            customer_profile_id=str(refreshed_order.customer_profile_id),
            total_amount=float(refreshed_order.total_amount),
        )

        # Real-time WebSocket broadcast to kitchen terminals (ADR-0010)
        await OrderEventPublisher(self.session).publish(
            branch_id=refreshed_order.branch_id,
            event="ORDER_PLACED",
            payload={
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
        await OrderEventPublisher(self.session).publish(
            branch_id=refreshed_order.branch_id,
            event="ORDER_STATUS_CHANGED",
            payload={
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
        order = await self.order_repo.get_by_id_for_update(order_id)
        if not order:
            raise EntityNotFoundError("Order not found.", "ORDER_NOT_FOUND")
        if order.status not in {"PLACED", "ACCEPTED"}:
            raise DomainInvariantError("Order can no longer be cancelled.", "ORDER_NOT_CANCELLABLE")
        reservations = (
            (
                await self.session.execute(
                    select(StockReservation)
                    .where(
                        StockReservation.order_id == order_id,
                        StockReservation.status == "RESERVED",
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for reservation in reservations:
            inventory = await self.session.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == reservation.inventory_item_id)
                .with_for_update()
            )
            if inventory:
                previous = inventory.quantity
                inventory.quantity += reservation.quantity
                inventory.is_in_stock = True
                reservation.status = "RESTORED"
                reservation.restored_at = datetime.now(UTC)
                self.session.add(
                    InventoryLog(
                        inventory_item_id=inventory.id,
                        change_amount=reservation.quantity,
                        previous_quantity=previous,
                        new_quantity=inventory.quantity,
                        reason=f"ORDER_CANCELLED:{order_id}",
                    )
                )
        order.cancellation_reason = reason
        await self.session.flush()
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
