import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cart.models import Cart, CartItem
from app.menu.models import MenuItem


class CartRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_customer_id(self, customer_profile_id: uuid.UUID) -> Cart | None:
        pass

    @abstractmethod
    async def get_by_id(self, cart_id: uuid.UUID) -> Cart | None:
        pass

    @abstractmethod
    async def create_cart(self, cart: Cart) -> Cart:
        pass

    @abstractmethod
    async def get_item(
        self, cart_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> CartItem | None:
        pass

    @abstractmethod
    async def get_item_by_id(self, item_id: uuid.UUID) -> CartItem | None:
        pass

    @abstractmethod
    async def add_item(self, item: CartItem) -> CartItem:
        pass

    @abstractmethod
    async def update_item(self, item: CartItem, update_data: dict) -> CartItem:
        pass

    @abstractmethod
    async def delete_item(self, item_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def clear_cart(self, cart_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def delete_cart(self, cart_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def delete_expired_carts(self, max_age_days: int = 7) -> int:
        pass

    @abstractmethod
    async def get_menu_item(self, menu_item_id: uuid.UUID) -> MenuItem | None:
        pass


class CartRepository(CartRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_customer_id(self, customer_profile_id: uuid.UUID) -> Cart | None:
        stmt = (
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
            .execution_options(populate_existing=True)
            .where(Cart.customer_profile_id == customer_profile_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, cart_id: uuid.UUID) -> Cart | None:
        stmt = (
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
            .execution_options(populate_existing=True)
            .where(Cart.id == cart_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_cart(self, cart: Cart) -> Cart:
        self.session.add(cart)
        await self.session.flush()
        await self.session.refresh(cart, attribute_names=["items"])
        return cart

    async def get_item(
        self, cart_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> CartItem | None:
        stmt = (
            select(CartItem)
            .options(selectinload(CartItem.menu_item))
            .where(CartItem.cart_id == cart_id, CartItem.menu_item_id == menu_item_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_item_by_id(self, item_id: uuid.UUID) -> CartItem | None:
        stmt = (
            select(CartItem)
            .options(selectinload(CartItem.menu_item))
            .where(CartItem.id == item_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_item(self, item: CartItem) -> CartItem:
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["menu_item"])
        return item

    async def update_item(self, item: CartItem, update_data: dict) -> CartItem:
        for key, val in update_data.items():
            if hasattr(item, key) and val is not None:
                setattr(item, key, val)
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["menu_item"])
        return item

    async def delete_item(self, item_id: uuid.UUID) -> None:
        stmt = delete(CartItem).where(CartItem.id == item_id)
        await self.session.execute(stmt)

    async def clear_cart(self, cart_id: uuid.UUID) -> None:
        stmt = delete(CartItem).where(CartItem.cart_id == cart_id)
        await self.session.execute(stmt)

    async def delete_cart(self, cart_id: uuid.UUID) -> None:
        stmt = delete(Cart).where(Cart.id == cart_id)
        await self.session.execute(stmt)

    async def delete_expired_carts(self, max_age_days: int = 7) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        # Select expired cart IDs
        stmt_find = select(Cart.id).where(Cart.updated_at < cutoff)
        res = await self.session.execute(stmt_find)
        expired_ids = res.scalars().all()
        if not expired_ids:
            return 0

        await self.session.execute(delete(Cart).where(Cart.id.in_(expired_ids)))
        return len(expired_ids)

    async def get_menu_item(self, menu_item_id: uuid.UUID) -> MenuItem | None:
        stmt = select(MenuItem).where(
            MenuItem.id == menu_item_id, MenuItem.deleted_at.is_(None)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
