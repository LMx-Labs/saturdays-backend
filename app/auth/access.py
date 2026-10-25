"""Server-side resource authorization shared by restaurant routes."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserClaims
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.exceptions import EntityNotFoundError, ForbiddenError
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.review.models import Review


async def require_branch_access(
    session: AsyncSession, user: UserClaims, branch_id: uuid.UUID
) -> None:
    if user.role == "PlatformAdmin":
        return
    if user.role in {"BranchManager", "KitchenStaff"}:
        if user.branch_id == str(branch_id):
            return
    elif user.role == "MerchantOwner":
        stmt = (
            select(Branch.id)
            .join(Brand, Branch.brand_id == Brand.id)
            .join(Merchant, Brand.merchant_id == Merchant.id)
            .where(
                Branch.id == branch_id,
                Merchant.owner_user_id == uuid.UUID(user.sub),
                Branch.deleted_at.is_(None),
                Brand.deleted_at.is_(None),
                Merchant.deleted_at.is_(None),
            )
        )
        if (await session.scalar(stmt)) is not None:
            return
    raise ForbiddenError("Branch access denied.", "BRANCH_ACCESS_FORBIDDEN")


async def require_menu_category_access(
    session: AsyncSession, user: UserClaims, category_id: uuid.UUID
) -> None:
    branch_id = await session.scalar(
        select(Menu.branch_id)
        .join(MenuCategory, MenuCategory.menu_id == Menu.id)
        .where(MenuCategory.id == category_id, MenuCategory.deleted_at.is_(None))
    )
    if branch_id is None:
        raise EntityNotFoundError("Category not found.", "CATEGORY_NOT_FOUND")
    await require_branch_access(session, user, branch_id)


async def require_menu_item_access(
    session: AsyncSession, user: UserClaims, item_id: uuid.UUID
) -> None:
    branch_id = await session.scalar(
        select(Menu.branch_id)
        .join(MenuCategory, MenuCategory.menu_id == Menu.id)
        .join(MenuItem, MenuItem.category_id == MenuCategory.id)
        .where(MenuItem.id == item_id, MenuItem.deleted_at.is_(None))
    )
    if branch_id is None:
        raise EntityNotFoundError("Item not found.", "MENU_ITEM_NOT_FOUND")
    await require_branch_access(session, user, branch_id)


async def require_menu_item_in_branch(
    session: AsyncSession, user: UserClaims, item_id: uuid.UUID, branch_id: uuid.UUID
) -> None:
    item_branch = await session.scalar(
        select(Menu.branch_id)
        .join(MenuCategory, MenuCategory.menu_id == Menu.id)
        .join(MenuItem, MenuItem.category_id == MenuCategory.id)
        .where(MenuItem.id == item_id, MenuItem.deleted_at.is_(None))
    )
    if item_branch != branch_id:
        raise ForbiddenError("Item is not in this branch.", "MENU_BRANCH_MISMATCH")
    await require_branch_access(session, user, branch_id)


async def require_inventory_access(
    session: AsyncSession, user: UserClaims, inventory_id: uuid.UUID
) -> None:
    branch_id = await session.scalar(
        select(InventoryItem.branch_id).where(
            InventoryItem.id == inventory_id, InventoryItem.deleted_at.is_(None)
        )
    )
    if branch_id is None:
        raise EntityNotFoundError("Inventory not found.", "INVENTORY_NOT_FOUND")
    await require_branch_access(session, user, branch_id)


async def require_kitchen_access(
    session: AsyncSession, user: UserClaims, kitchen_id: uuid.UUID
) -> None:
    branch_id = await session.scalar(
        select(Kitchen.branch_id).where(
            Kitchen.id == kitchen_id, Kitchen.deleted_at.is_(None)
        )
    )
    if branch_id is None:
        raise EntityNotFoundError("Kitchen not found.", "KITCHEN_NOT_FOUND")
    await require_branch_access(session, user, branch_id)


async def require_review_access(
    session: AsyncSession, user: UserClaims, review_id: uuid.UUID
) -> None:
    branch_id = await session.scalar(
        select(Review.branch_id).where(
            Review.id == review_id, Review.deleted_at.is_(None)
        )
    )
    if branch_id is None:
        raise EntityNotFoundError("Review not found.", "REVIEW_NOT_FOUND")
    await require_branch_access(session, user, branch_id)
