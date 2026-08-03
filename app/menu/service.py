import uuid
from abc import ABC, abstractmethod

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainInvariantError, EntityNotFoundError
from app.menu.models import Menu, MenuCategory, MenuItem
from app.menu.repository import MenuRepositoryInterface
from app.menu.schemas import (
    MenuCategoryCreate,
    MenuCreate,
    MenuItemCreate,
    MenuItemUpdate,
)

logger = structlog.get_logger()


class MenuServiceInterface(ABC):
    @abstractmethod
    async def get_branch_menu(self, branch_id: uuid.UUID) -> Menu:
        pass

    @abstractmethod
    async def create_branch_menu(self, branch_id: uuid.UUID, req: MenuCreate) -> Menu:
        pass

    @abstractmethod
    async def create_category(
        self, branch_id: uuid.UUID, req: MenuCategoryCreate
    ) -> MenuCategory:
        pass

    @abstractmethod
    async def create_menu_item(
        self, branch_id: uuid.UUID, req: MenuItemCreate
    ) -> MenuItem:
        pass

    @abstractmethod
    async def get_menu_item(self, item_id: uuid.UUID) -> MenuItem:
        pass

    @abstractmethod
    async def update_menu_item(
        self, item_id: uuid.UUID, req: MenuItemUpdate
    ) -> MenuItem:
        pass


class MenuService(MenuServiceInterface):
    def __init__(self, session: AsyncSession, menu_repo: MenuRepositoryInterface):
        self.session = session
        self.menu_repo = menu_repo

    async def get_branch_menu(self, branch_id: uuid.UUID) -> Menu:
        menu = await self.menu_repo.get_menu_by_branch_id(branch_id)
        if not menu or not menu.is_active:
            raise EntityNotFoundError(
                message=f"Active menu for branch '{branch_id}' not found.",
                error_code="MENU_NOT_FOUND",
            )
        return menu

    async def create_branch_menu(self, branch_id: uuid.UUID, req: MenuCreate) -> Menu:
        existing = await self.menu_repo.get_menu_by_branch_id(branch_id)
        if existing:
            return existing

        menu = await self.menu_repo.create_menu(branch_id=branch_id, name=req.name)
        await self.session.commit()
        return menu

    async def create_category(
        self, branch_id: uuid.UUID, req: MenuCategoryCreate
    ) -> MenuCategory:
        menu = await self.menu_repo.get_menu_by_branch_id(branch_id)
        if not menu:
            menu = await self.menu_repo.create_menu(branch_id=branch_id)

        category = await self.menu_repo.create_category(
            menu_id=menu.id, name=req.name, display_order=req.display_order
        )
        await self.session.commit()
        return category

    async def create_menu_item(
        self, branch_id: uuid.UUID, req: MenuItemCreate
    ) -> MenuItem:
        # INV-MENU-001: Non-Negative Base Price
        if req.base_price < 0.0:
            raise DomainInvariantError(
                message="Base price must be greater than or equal to 0.00.",
                error_code="NEGATIVE_BASE_PRICE",
            )

        # INV-MENU-002: Valid Category Hierarchy
        category = await self.menu_repo.get_category_by_id(req.category_id)
        if not category:
            raise EntityNotFoundError(
                message=f"Category with ID '{req.category_id}' not found.",
                error_code="CATEGORY_NOT_FOUND",
            )

        if category.menu is None or category.menu.branch_id != branch_id:
            raise DomainInvariantError(
                message="Category does not belong to the specified branch menu.",
                error_code="INVALID_CATEGORY_HIERARCHY",
            )

        item = MenuItem(
            category_id=req.category_id,
            name=req.name,
            description=req.description,
            base_price=req.base_price,
            image_url=req.image_url,
            is_available=req.is_available,
            is_veg=req.is_veg,
        )

        created_item = await self.menu_repo.create_menu_item(item)
        await self.session.commit()

        logger.info(
            "MenuItemCreatedEvent",
            menu_item_id=str(created_item.id),
            branch_id=str(branch_id),
            base_price=float(created_item.base_price),
        )

        return created_item

    async def get_menu_item(self, item_id: uuid.UUID) -> MenuItem:
        item = await self.menu_repo.get_menu_item_by_id(item_id)
        if not item:
            raise EntityNotFoundError(
                message=f"Menu item '{item_id}' not found.",
                error_code="MENU_ITEM_NOT_FOUND",
            )
        return item

    async def update_menu_item(
        self, item_id: uuid.UUID, req: MenuItemUpdate
    ) -> MenuItem:
        item = await self.get_menu_item(item_id)

        if req.base_price is not None:
            if req.base_price < 0.0:
                raise DomainInvariantError(
                    message="Base price must be greater than or equal to 0.00.",
                    error_code="NEGATIVE_BASE_PRICE",
                )
            item.base_price = req.base_price

        if req.name is not None:
            item.name = req.name
        if req.description is not None:
            item.description = req.description
        if req.image_url is not None:
            item.image_url = req.image_url
        if req.is_available is not None:
            item.is_available = req.is_available
        if req.is_veg is not None:
            item.is_veg = req.is_veg

        updated = await self.menu_repo.update_menu_item(item)
        await self.session.commit()
        return updated
