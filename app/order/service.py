import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.admin.models import SystemFeatureFlag
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    DomainInvariantError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.credit.service import StoreCreditService
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem, InventoryLog
from app.kitchen.models import Kitchen
from app.menu.models import MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.order.models import Order, OrderItem, OrderReservation
from app.order.pricing import PriceLine, calculate_price, money
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
        idempotency_key: str,
    ) -> Order:
        pass

    @abstractmethod
    async def update_order_status(
        self,
        order_id: uuid.UUID,
        changed_by_user_id: uuid.UUID,
        target_status: str,
        actor_role: str | None = None,
    ) -> Order:
        pass

    @abstractmethod
    async def cancel_order(
        self,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
        actor_role: str | None = None,
    ) -> Order:
        pass

    @abstractmethod
    async def get_order(self, order_id: uuid.UUID) -> Order:
        pass

    @abstractmethod
    async def get_customer_orders(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[Order]:
        pass

    @abstractmethod
    async def get_branch_orders(
        self,
        branch_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
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
        idempotency_key: str,
    ) -> Order:
        fingerprint = hashlib.sha256(
            json.dumps(
                req.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        # Serialize retries for a customer before any inventory or credit changes.
        await self.session.execute(
            select(CustomerProfile.id)
            .where(CustomerProfile.id == customer_profile_id)
            .with_for_update()
        )
        prior = await self.session.scalar(
            select(Order.id).where(
                Order.customer_profile_id == customer_profile_id,
                Order.idempotency_key == idempotency_key,
            )
        )
        if prior is not None:
            existing = await self.get_order(prior)
            if existing.request_fingerprint != fingerprint:
                raise ConflictError(
                    "Idempotency key was used for a different order.",
                    "IDEMPOTENCY_CONFLICT",
                )
            return existing

        branch = await self.session.scalar(
            select(Branch).where(
                Branch.id == req.branch_id, Branch.deleted_at.is_(None)
            )
        )
        if branch is None or not branch.is_active:
            raise DomainInvariantError(
                "Branch is not open for orders.", "BRANCH_OFFLINE"
            )
        approved = await self.session.scalar(
            select(Merchant.id)
            .join(Brand, Brand.merchant_id == Merchant.id)
            .where(Brand.id == branch.brand_id, Merchant.status == "APPROVED")
        )
        if approved is None:
            raise DomainInvariantError(
                "Merchant is not approved for orders.", "MERCHANT_NOT_APPROVED"
            )
        if get_settings().EMERGENCY_MAINTENANCE_MODE:
            raise DomainInvariantError(
                "Checkout is paused for maintenance.", "MAINTENANCE_MODE"
            )
        maintenance = await self.session.get(
            SystemFeatureFlag, "EMERGENCY_MAINTENANCE_MODE"
        )
        if maintenance is not None and maintenance.enabled:
            raise DomainInvariantError(
                "Checkout is paused for maintenance.", "MAINTENANCE_MODE"
            )
        local_time = (
            datetime.now(UTC)
            .astimezone(ZoneInfo(branch.timezone_name))
            .time()
            .replace(tzinfo=None)
        )
        opening, closing = branch.opening_time, branch.closing_time
        is_open = (
            True
            if opening == closing
            else (
                opening <= local_time <= closing
                if opening < closing
                else local_time >= opening or local_time <= closing
            )
        )
        if not is_open:
            raise DomainInvariantError(
                "Branch is outside operating hours.", "BRANCH_CLOSED"
            )
        kitchen = await self.session.scalar(
            select(Kitchen.id)
            .where(
                Kitchen.branch_id == req.branch_id,
                Kitchen.is_active.is_(True),
                Kitchen.deleted_at.is_(None),
            )
            .limit(1)
        )
        if kitchen is None:
            raise DomainInvariantError(
                "No active kitchen is available.", "KITCHEN_UNAVAILABLE"
            )

        price_lines: list[PriceLine] = []
        order_items: list[OrderItem] = []
        requested_ids: set[uuid.UUID] = set()
        reservations: list[tuple[uuid.UUID, int]] = []
        admitted_items: list[tuple[MenuItem, int, list[dict] | None, Decimal]] = []

        for item_req in sorted(req.items, key=lambda item: str(item.menu_item_id)):
            if item_req.menu_item_id in requested_ids:
                raise DomainInvariantError(
                    "Duplicate menu item in order.", "DUPLICATE_ORDER_ITEM"
                )
            requested_ids.add(item_req.menu_item_id)
            if item_req.selected_modifiers_snapshot:
                raise DomainInvariantError(
                    "Selected modifiers are not supported for checkout.",
                    "UNSUPPORTED_MODIFIERS",
                )
            # Fetch menu item details for snapshot and branch invariant check
            stmt = (
                select(MenuItem)
                .where(
                    MenuItem.id == item_req.menu_item_id,
                    MenuItem.deleted_at.is_(None),
                )
                .options(
                    selectinload(MenuItem.category).selectinload(MenuCategory.menu)
                )
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
                menu_item.category is None
                or menu_item.category.menu is None
                or menu_item.category.menu.branch_id != req.branch_id
            ):
                raise DomainInvariantError(
                    message=f"Menu item '{menu_item.id}' does not belong to branch '{req.branch_id}'.",
                    error_code="CROSS_BRANCH_ORDER_VIOLATION",
                )

            if (
                not menu_item.is_available
                or menu_item.category.deleted_at is not None
                or menu_item.category.menu.deleted_at is not None
                or not menu_item.category.menu.is_active
            ):
                raise DomainInvariantError(
                    "Menu item is unavailable.", "ITEM_UNAVAILABLE"
                )
            unit_price = money(Decimal(str(menu_item.base_price)))
            price_lines.append(
                PriceLine(unit_price=unit_price, quantity=item_req.quantity)
            )

            admitted_items.append(
                (
                    menu_item,
                    item_req.quantity,
                    item_req.selected_modifiers_snapshot,
                    unit_price,
                )
            )

        # Validate every line before changing stock. A later admission error must
        # never leave an earlier line's reservation in the active transaction.
        inventory_rows = (
            await self.session.execute(
                select(InventoryItem.id, InventoryItem.menu_item_id).where(
                    InventoryItem.branch_id == req.branch_id,
                    InventoryItem.menu_item_id.in_(requested_ids),
                    InventoryItem.deleted_at.is_(None),
                )
            )
        ).all()
        inventory_by_menu = {
            menu_id: inventory_id for inventory_id, menu_id in inventory_rows
        }
        if len(inventory_by_menu) != len(requested_ids):
            raise DomainInvariantError(
                "Insufficient stock for order.", "INSUFFICIENT_STOCK"
            )
        for menu_item, quantity, modifiers_snapshot, unit_price in sorted(
            admitted_items, key=lambda line: str(inventory_by_menu[line[0].id])
        ):
            result = await self.session.execute(
                update(InventoryItem)
                .where(
                    InventoryItem.id == inventory_by_menu[menu_item.id],
                    InventoryItem.branch_id == req.branch_id,
                    InventoryItem.deleted_at.is_(None),
                    InventoryItem.is_in_stock.is_(True),
                    InventoryItem.quantity >= quantity,
                )
                .values(
                    quantity=InventoryItem.quantity - quantity,
                    is_in_stock=case(
                        (InventoryItem.quantity == quantity, False),
                        else_=True,
                    ),
                )
                .returning(InventoryItem.id, InventoryItem.quantity)
            )
            reserved = result.first()
            if reserved is None:
                await self.session.rollback()
                raise DomainInvariantError(
                    "Insufficient stock for order.", "INSUFFICIENT_STOCK"
                )
            inventory_id, new_quantity = reserved
            reservations.append((inventory_id, quantity))
            self.session.add(
                InventoryLog(
                    inventory_item_id=inventory_id,
                    change_amount=-quantity,
                    previous_quantity=new_quantity + quantity,
                    new_quantity=new_quantity,
                    reason="ORDER_RESERVATION",
                )
            )

            order_item = OrderItem(
                menu_item_id=menu_item.id,
                item_name_snapshot=menu_item.name,
                unit_price_snapshot=unit_price,
                quantity=quantity,
                selected_modifiers_snapshot=modifiers_snapshot,
            )
            order_items.append(order_item)

        price = calculate_price(price_lines)
        order = Order(
            customer_profile_id=customer_profile_id,
            branch_id=req.branch_id,
            total_amount=price.total,
            price_breakdown_snapshot=price.snapshot(),
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            status="PLACED",
            delivery_address_snapshot=req.delivery_address_snapshot,
        )

        created_order = await self.order_repo.create_order(
            order=order,
            items=order_items,
            user_id=user_id,
        )
        for inventory_id, quantity in reservations:
            self.session.add(
                OrderReservation(
                    order_id=created_order.id,
                    inventory_item_id=inventory_id,
                    quantity=quantity,
                )
            )

        if req.use_store_credit and order.total_amount > 0:
            credit_service = StoreCreditService(self.session)
            brand_id = await credit_service.brand_id_for_branch(req.branch_id)
            applied = await credit_service.redeem(
                customer_profile_id=customer_profile_id,
                brand_id=brand_id,
                max_amount=float(order.total_amount),
                order_id=created_order.id,
            )
            created_order.store_credit_applied = applied

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
        actor_role: str | None = None,
    ) -> Order:
        order = await self.order_repo.get_by_id_for_update(order_id)
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

        # Resolve actor role if not explicitly provided
        if actor_role is None:
            user = await self.session.get(User, changed_by_user_id)
            if user:
                actor_role = user.role

        # Enforce Customer cancellation only while PLACED (inside transaction after locking order row)
        if target_status == "CANCELLED" and actor_role == "Customer":
            if current_status != "PLACED":
                raise DomainInvariantError(
                    message="Customers may only cancel orders in PLACED status prior to merchant acceptance.",
                    error_code="CUSTOMER_CANCELLATION_WINDOW_EXPIRED",
                )
        elif actor_role == "Customer" and target_status != "CANCELLED":
            raise ForbiddenError(
                message=f"Role 'Customer' cannot set status '{target_status}'.",
                error_code="ORDER_STATUS_FORBIDDEN",
            )

        if target_status == "CANCELLED":
            settled = await StoreCreditService(self.session).net_captured_amount(
                order_id
            )
            if settled > 0:
                raise ConflictError(
                    "Cancellation of a paid order requires a confirmed refund policy.",
                    "PAID_CANCELLATION_REQUIRES_POLICY",
                )

        updated_order = await self.order_repo.update_order_status(
            order_id=order_id,
            new_status=target_status,
            changed_by_user_id=changed_by_user_id,
        )
        if target_status == "CANCELLED":
            holds = (
                (
                    await self.session.execute(
                        select(OrderReservation)
                        .where(
                            OrderReservation.order_id == order_id,
                            OrderReservation.released_at.is_(None),
                        )
                        .order_by(OrderReservation.inventory_item_id)
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for hold in holds:
                inventory = await self.session.scalar(
                    select(InventoryItem)
                    .where(InventoryItem.id == hold.inventory_item_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if inventory is None:
                    raise DomainInvariantError(
                        "Reserved inventory record is missing.",
                        "RESERVATION_INVENTORY_MISSING",
                    )
                previous = inventory.quantity
                inventory.quantity += hold.quantity
                inventory.is_in_stock = (
                    inventory.quantity > 0 and not inventory.is_paused
                )
                hold.released_at = datetime.now(UTC)
                self.session.add(
                    InventoryLog(
                        inventory_item_id=inventory.id,
                        change_amount=hold.quantity,
                        previous_quantity=previous,
                        new_quantity=inventory.quantity,
                        reason="ORDER_CANCELLATION",
                    )
                )

        # Existing store credit allocations are returned in the same transaction.
        # Captured payments are blocked above until the refund policy is agreed.
        if target_status == "CANCELLED":
            await StoreCreditService(self.session).issue_for_cancelled_order(
                updated_order
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
        actor_role: str | None = None,
    ) -> Order:
        return await self.update_order_status(
            order_id=order_id,
            changed_by_user_id=user_id,
            target_status="CANCELLED",
            actor_role=actor_role,
        )

    async def get_order(self, order_id: uuid.UUID) -> Order:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise EntityNotFoundError(
                message=f"Order '{order_id}' not found.",
                error_code="ORDER_NOT_FOUND",
            )
        return order

    async def get_customer_orders(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[Order]:
        return await self.order_repo.get_customer_orders(customer_profile_id)

    async def get_branch_orders(
        self,
        branch_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Order]:
        return await self.order_repo.get_branch_orders(branch_id, status, skip, limit)
