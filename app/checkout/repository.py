import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.branch.models import Branch
from app.cart.models import Cart
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen


class CheckoutRepositoryInterface(ABC):
    """Abstract repository for Checkout read operations."""

    @abstractmethod
    async def get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        """Fetch branch entity."""

    @abstractmethod
    async def get_kitchen_for_branch(self, branch_id: uuid.UUID) -> Kitchen | None:
        """Fetch active kitchen for a branch."""

    @abstractmethod
    async def get_customer_profile(self, user_id: uuid.UUID) -> CustomerProfile | None:
        """Fetch customer profile by user ID."""

    @abstractmethod
    async def get_cart_with_items(self, cart_id: uuid.UUID) -> Cart | None:
        """Fetch cart entity with eager loaded items and menu items."""

    @abstractmethod
    async def get_inventory_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> InventoryItem | None:
        """Fetch inventory item stock status."""


class CheckoutRepository(CheckoutRepositoryInterface):
    """Concrete SQLAlchemy implementation of CheckoutRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        stmt = select(Branch).where(
            Branch.id == branch_id,
            Branch.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_kitchen_for_branch(self, branch_id: uuid.UUID) -> Kitchen | None:
        stmt = select(Kitchen).where(
            Kitchen.branch_id == branch_id,
            Kitchen.is_active.is_(True),
            Kitchen.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_customer_profile(self, user_id: uuid.UUID) -> CustomerProfile | None:
        stmt = select(CustomerProfile).where(
            CustomerProfile.user_id == user_id,
            CustomerProfile.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_cart_with_items(self, cart_id: uuid.UUID) -> Cart | None:
        stmt = (
            select(Cart)
            .options(
                selectinload(Cart.items),
            )
            .where(Cart.id == cart_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_inventory_item(
        self, branch_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.branch_id == branch_id,
            InventoryItem.menu_item_id == menu_item_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
