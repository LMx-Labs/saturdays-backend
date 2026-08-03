import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.inventory.models import InventoryItem
from app.inventory.repository import InventoryRepositoryInterface
from app.inventory.schemas import (
    InventoryItemCreateRequest,
    StockUpdateRequest,
)

logger = structlog.get_logger()


class InventoryServiceInterface(ABC):
    @abstractmethod
    async def get_branch_inventory(
        self, branch_id: uuid.UUID
    ) -> Sequence[InventoryItem]:
        pass

    @abstractmethod
    async def create_inventory_item(
        self, branch_id: uuid.UUID, req: InventoryItemCreateRequest
    ) -> InventoryItem:
        pass

    @abstractmethod
    async def update_stock(
        self, inventory_item_id: uuid.UUID, req: StockUpdateRequest
    ) -> InventoryItem:
        pass

    @abstractmethod
    async def reserve_stock(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, quantity: int
    ) -> InventoryItem:
        pass


class InventoryService(InventoryServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        inventory_repo: InventoryRepositoryInterface,
    ):
        self.session = session
        self.inventory_repo = inventory_repo

    async def get_branch_inventory(
        self, branch_id: uuid.UUID
    ) -> Sequence[InventoryItem]:
        return await self.inventory_repo.get_branch_inventory(branch_id)

    async def create_inventory_item(
        self, branch_id: uuid.UUID, req: InventoryItemCreateRequest
    ) -> InventoryItem:
        item = await self.inventory_repo.create_item(
            branch_id=branch_id,
            menu_item_id=req.menu_item_id,
            initial_quantity=req.initial_quantity,
        )
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_stock(
        self, inventory_item_id: uuid.UUID, req: StockUpdateRequest
    ) -> InventoryItem:
        # INV-0002 & INV-INV-001: Enforce non-negative quantity & track adjustments
        item = await self.inventory_repo.update_item_stock(
            inventory_item_id=inventory_item_id,
            new_quantity=req.quantity,
            reason=req.reason,
            is_in_stock=req.is_in_stock,
        )
        await self.session.commit()
        await self.session.refresh(item)

        if item.quantity == 0 or not item.is_in_stock:
            logger.info(
                "InventoryDepletedEvent",
                branch_id=str(item.branch_id),
                menu_item_id=str(item.menu_item_id),
                status="OUT_OF_STOCK",
            )

        return item

    async def reserve_stock(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID, quantity: int
    ) -> InventoryItem:
        # Enforces pessimistic row locking (SELECT FOR UPDATE) via repository
        item = await self.inventory_repo.reserve_stock(
            branch_id=branch_id,
            menu_item_id=menu_item_id,
            quantity=quantity,
        )
        await self.session.commit()
        await self.session.refresh(item)

        if item.quantity == 0 or not item.is_in_stock:
            logger.info(
                "InventoryDepletedEvent",
                branch_id=str(item.branch_id),
                menu_item_id=str(item.menu_item_id),
                status="OUT_OF_STOCK",
            )

        return item
