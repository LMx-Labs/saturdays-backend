import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.menu.models import Menu, MenuCategory, MenuItem


class MenuRepositoryInterface(ABC):
    @abstractmethod
    async def get_menu_by_branch_id(self, branch_id: uuid.UUID) -> Menu | None:
        pass

    @abstractmethod
    async def create_menu(self, branch_id: uuid.UUID, name: str = "Main Menu") -> Menu:
        pass

    @abstractmethod
    async def get_category_by_id(self, category_id: uuid.UUID) -> MenuCategory | None:
        pass

    @abstractmethod
    async def create_category(
        self, menu_id: uuid.UUID, name: str, display_order: int = 0
    ) -> MenuCategory:
        pass

    @abstractmethod
    async def create_menu_item(self, item: MenuItem) -> MenuItem:
        pass

    @abstractmethod
    async def get_menu_item_by_id(self, item_id: uuid.UUID) -> MenuItem | None:
        pass

    @abstractmethod
    async def update_menu_item(self, item: MenuItem) -> MenuItem:
        pass


class MenuRepository(MenuRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_menu_by_branch_id(self, branch_id: uuid.UUID) -> Menu | None:
        stmt = (
            select(Menu)
            .where(Menu.branch_id == branch_id, Menu.deleted_at.is_(None))
            .options(
                selectinload(Menu.categories)
                .selectinload(MenuCategory.items)
                .selectinload(MenuItem.modifiers)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_menu(self, branch_id: uuid.UUID, name: str = "Main Menu") -> Menu:
        menu = Menu(branch_id=branch_id, name=name, is_active=True)
        self.session.add(menu)
        await self.session.flush()
        return menu

    async def get_category_by_id(self, category_id: uuid.UUID) -> MenuCategory | None:
        stmt = (
            select(MenuCategory)
            .where(MenuCategory.id == category_id, MenuCategory.deleted_at.is_(None))
            .options(selectinload(MenuCategory.menu))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_category(
        self, menu_id: uuid.UUID, name: str, display_order: int = 0
    ) -> MenuCategory:
        category = MenuCategory(menu_id=menu_id, name=name, display_order=display_order)
        self.session.add(category)
        await self.session.flush()
        return category

    async def create_menu_item(self, item: MenuItem) -> MenuItem:
        self.session.add(item)
        await self.session.flush()
        stmt = (
            select(MenuItem).where(MenuItem.id == item.id).options(selectinload(MenuItem.modifiers))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_menu_item_by_id(self, item_id: uuid.UUID) -> MenuItem | None:
        stmt = (
            select(MenuItem)
            .where(MenuItem.id == item_id, MenuItem.deleted_at.is_(None))
            .options(selectinload(MenuItem.modifiers), selectinload(MenuItem.category))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_menu_item(self, item: MenuItem) -> MenuItem:
        self.session.add(item)
        await self.session.flush()
        return item
