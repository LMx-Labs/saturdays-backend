import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch
from app.brand.models import Brand
from app.menu.models import Menu, MenuCategory, MenuItem


class SearchRepositoryInterface(ABC):
    """Abstract repository interface for Search read operations."""

    @abstractmethod
    async def search_branches(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        is_active_only: bool = True,
        current_time: datetime | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[Branch, Brand]]:
        """Query active branches and parent brands."""

    @abstractmethod
    async def search_menu_items(
        self,
        q: str | None = None,
        is_veg: bool | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        is_active_only: bool = True,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[MenuItem, MenuCategory, Menu, Branch, Brand]]:
        """Query active menu items with parent category, menu, branch, and brand."""

    @abstractmethod
    async def search_categories(
        self,
        q: str | None = None,
        is_active_only: bool = True,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[MenuCategory, Menu, Branch, Brand]]:
        """Query active menu categories."""

    @abstractmethod
    async def get_typeahead_suggestions(
        self, q: str, limit: int = 10
    ) -> list[tuple[str, str, uuid.UUID | None]]:
        """Fetch typeahead suggestions (text, type, entity_id)."""


class SearchRepository(SearchRepositoryInterface):
    """Concrete SQLAlchemy implementation of SearchRepositoryInterface."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_branches(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        is_active_only: bool = True,
        current_time: datetime | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[Branch, Brand]]:
        stmt = (
            select(Branch, Brand)
            .join(Brand, Branch.brand_id == Brand.id)
            .where(
                Branch.deleted_at.is_(None),
                Brand.deleted_at.is_(None),
            )
        )

        # INV-SRCH-001: Active Store Filter Enforcement
        if is_active_only:
            stmt = stmt.where(Branch.is_active.is_(True))
            if current_time:
                t = current_time.time()
                stmt = stmt.where(
                    Branch.opening_time <= t,
                    Branch.closing_time >= t,
                )

        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                (Branch.name.ilike(pattern))
                | (Brand.name.ilike(pattern))
                | (Brand.description.ilike(pattern))
            )

        if cuisine:
            pattern_c = f"%{cuisine}%"
            stmt = stmt.where(Brand.name.ilike(pattern_c))

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def search_menu_items(
        self,
        q: str | None = None,
        is_veg: bool | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        is_active_only: bool = True,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[MenuItem, MenuCategory, Menu, Branch, Brand]]:
        stmt = (
            select(MenuItem, MenuCategory, Menu, Branch, Brand)
            .join(MenuCategory, MenuItem.category_id == MenuCategory.id)
            .join(Menu, MenuCategory.menu_id == Menu.id)
            .join(Branch, Menu.branch_id == Branch.id)
            .join(Brand, Branch.brand_id == Brand.id)
            .where(
                MenuItem.deleted_at.is_(None),
                MenuCategory.deleted_at.is_(None),
                Menu.deleted_at.is_(None),
                Branch.deleted_at.is_(None),
                Brand.deleted_at.is_(None),
            )
        )

        if is_active_only:
            stmt = stmt.where(Branch.is_active.is_(True), Menu.is_active.is_(True))

        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                (MenuItem.name.ilike(pattern))
                | (MenuItem.description.ilike(pattern))
                | (MenuCategory.name.ilike(pattern))
            )

        if is_veg is not None:
            stmt = stmt.where(MenuItem.is_veg == is_veg)

        if min_price is not None:
            stmt = stmt.where(MenuItem.base_price >= min_price)

        if max_price is not None:
            stmt = stmt.where(MenuItem.base_price <= max_price)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2], row[3], row[4]) for row in result.all()]

    async def search_categories(
        self,
        q: str | None = None,
        is_active_only: bool = True,
        skip: int = 0,
        limit: int = 20,
    ) -> list[tuple[MenuCategory, Menu, Branch, Brand]]:
        stmt = (
            select(MenuCategory, Menu, Branch, Brand)
            .join(Menu, MenuCategory.menu_id == Menu.id)
            .join(Branch, Menu.branch_id == Branch.id)
            .join(Brand, Branch.brand_id == Brand.id)
            .where(
                MenuCategory.deleted_at.is_(None),
                Menu.deleted_at.is_(None),
                Branch.deleted_at.is_(None),
                Brand.deleted_at.is_(None),
            )
        )

        if is_active_only:
            stmt = stmt.where(Branch.is_active.is_(True), Menu.is_active.is_(True))

        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(MenuCategory.name.ilike(pattern))

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def get_typeahead_suggestions(
        self, q: str, limit: int = 10
    ) -> list[tuple[str, str, uuid.UUID | None]]:
        suggestions: list[tuple[str, str, uuid.UUID | None]] = []
        pattern = f"%{q}%"

        # 1. Matching Branch names
        stmt_branch = (
            select(Branch.name, Branch.id)
            .where(
                Branch.deleted_at.is_(None),
                Branch.is_active.is_(True),
                Branch.name.ilike(pattern),
            )
            .limit(limit)
        )
        res_branch = await self.session.execute(stmt_branch)
        for name, bid in res_branch.all():
            suggestions.append((name, "restaurant", bid))

        # 2. Matching Dish names
        stmt_item = (
            select(MenuItem.name, MenuItem.id)
            .where(
                MenuItem.deleted_at.is_(None),
                MenuItem.name.ilike(pattern),
            )
            .limit(limit)
        )
        res_item = await self.session.execute(stmt_item)
        for name, iid in res_item.all():
            suggestions.append((name, "dish", iid))

        # 3. Matching Brand names
        stmt_brand = (
            select(Brand.name, Brand.id)
            .where(
                Brand.deleted_at.is_(None),
                Brand.name.ilike(pattern),
            )
            .limit(limit)
        )
        res_brand = await self.session.execute(stmt_brand)
        for name, b_id in res_brand.all():
            suggestions.append((name, "brand", b_id))

        return suggestions[:limit]
