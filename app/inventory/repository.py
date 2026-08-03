import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainInvariantError, EntityNotFoundError
from app.inventory.models import InventoryItem, InventoryLog


class InventoryRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, inventory_item_id: uuid.UUID) -> InventoryItem | None:
        pass

    @abstractmethod
    async def get_by_branch_and_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> InventoryItem | None:
        pass

    @abstractmethod
    async def get_branch_inventory(
        self, branch_id: uuid.UUID
    ) -> Sequence[InventoryItem]:
        pass

    @abstractmethod
    async def create_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, initial_quantity: int = 0
    ) -> InventoryItem:
        pass

    @abstractmethod
    async def update_item_stock(
        self,
        inventory_item_id: uuid.UUID,
        new_quantity: int,
        reason: str,
        is_in_stock: bool | None = None,
    ) -> InventoryItem:
        pass

    @abstractmethod
    async def reserve_stock(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, quantity: int
    ) -> InventoryItem:
        pass


class InventoryRepository(InventoryRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, inventory_item_id: uuid.UUID) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.id == inventory_item_id,
            InventoryItem.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_branch_and_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.menu_item_id == menu_item_id,
            InventoryItem.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_branch_inventory(
        self, branch_id: uuid.UUID
    ) -> Sequence[InventoryItem]:
        stmt = select(InventoryItem).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, initial_quantity: int = 0
    ) -> InventoryItem:
        if initial_quantity < 0:
            raise DomainInvariantError(
                message="Initial stock quantity cannot be negative.",
                error_code="NEGATIVE_STOCK_QUANTITY",
            )

        existing = await self.get_by_branch_and_item(branch_id, menu_item_id)
        if existing:
            return existing

        item = InventoryItem(
            branch_id=branch_id,
            menu_item_id=menu_item_id,
            quantity=initial_quantity,
            is_in_stock=(initial_quantity > 0),
        )
        self.session.add(item)
        await self.session.flush()

        log = InventoryLog(
            inventory_item_id=item.id,
            change_amount=initial_quantity,
            previous_quantity=0,
            new_quantity=initial_quantity,
            reason="INITIAL_STOCK",
        )
        self.session.add(log)
        await self.session.flush()

        return item

    async def update_item_stock(
        self,
        inventory_item_id: uuid.UUID,
        new_quantity: int,
        reason: str,
        is_in_stock: bool | None = None,
    ) -> InventoryItem:
        if new_quantity < 0:
            raise DomainInvariantError(
                message="Stock quantity cannot be negative.",
                error_code="NEGATIVE_STOCK_QUANTITY",
            )

        # Enforce pessimistic row-level lock SELECT FOR UPDATE
        stmt = (
            select(InventoryItem)
            .where(
                InventoryItem.id == inventory_item_id,
                InventoryItem.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        item = result.scalars().first()

        if not item:
            raise EntityNotFoundError(
                message=f"Inventory item '{inventory_item_id}' not found.",
                error_code="INVENTORY_ITEM_NOT_FOUND",
            )

        prev_qty = item.quantity
        change_amount = new_quantity - prev_qty
        item.quantity = new_quantity
        if is_in_stock is not None:
            item.is_in_stock = is_in_stock
        else:
            item.is_in_stock = new_quantity > 0

        log = InventoryLog(
            inventory_item_id=item.id,
            change_amount=change_amount,
            previous_quantity=prev_qty,
            new_quantity=new_quantity,
            reason=reason,
        )
        self.session.add(log)
        await self.session.flush()
        return item

    async def reserve_stock(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, quantity: int
    ) -> InventoryItem:
        if quantity <= 0:
            raise DomainInvariantError(
                message="Stock reservation quantity must be greater than zero.",
                error_code="INVALID_RESERVATION_QUANTITY",
            )

        # Enforce pessimistic row-level lock SELECT FOR UPDATE exactly as specified
        stmt = (
            select(InventoryItem)
            .where(
                InventoryItem.branch_id == branch_id,
                InventoryItem.menu_item_id == menu_item_id,
                InventoryItem.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        item = result.scalars().first()

        if not item:
            raise EntityNotFoundError(
                message=f"Inventory record for item '{menu_item_id}' at branch '{branch_id}' not found.",
                error_code="INVENTORY_ITEM_NOT_FOUND",
            )

        if item.quantity < quantity or not item.is_in_stock:
            raise DomainInvariantError(
                message=f"Insufficient stock for menu item '{menu_item_id}'. Requested: {quantity}, Available: {item.quantity}.",
                error_code="INSUFFICIENT_STOCK",
            )

        prev_qty = item.quantity
        item.quantity -= quantity
        if item.quantity == 0:
            item.is_in_stock = False

        log = InventoryLog(
            inventory_item_id=item.id,
            change_amount=-quantity,
            previous_quantity=prev_qty,
            new_quantity=item.quantity,
            reason="ORDER_RESERVATION",
        )
        self.session.add(log)
        await self.session.flush()
        return item
