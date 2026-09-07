import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.authorization import require_branch_access
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.menu.models import Menu, MenuCategory, MenuItem, MenuModifier
from app.menu.repository import MenuRepository, MenuRepositoryInterface
from app.menu.schemas import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuCreate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MenuModifierCreate,
    MenuModifierResponse,
    MenuModifierUpdate,
    MenuResponse,
    MenuUpdate,
)
from app.menu.service import MenuService, MenuServiceInterface

router = APIRouter(prefix="", tags=["Menu"])

CATALOG_ROLES = ["BranchManager", "MerchantOwner", "PlatformAdmin"]


async def _item_branch(session: AsyncSession, item_id: uuid.UUID) -> tuple[MenuItem, uuid.UUID]:
    result = await session.execute(
        select(MenuItem, Menu.branch_id)
        .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .join(Menu, Menu.id == MenuCategory.menu_id)
        .where(MenuItem.id == item_id, MenuItem.deleted_at.is_(None))
        .options(selectinload(MenuItem.modifiers))
    )
    row = result.first()
    if not row:
        raise EntityNotFoundError("Menu item not found.", "MENU_ITEM_NOT_FOUND")
    return row[0], row[1]


def get_menu_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MenuRepositoryInterface:
    return MenuRepository(session=session)


def get_menu_service(
    session: AsyncSession = Depends(get_db_session),
    menu_repo: MenuRepositoryInterface = Depends(get_menu_repository),
) -> MenuServiceInterface:
    return MenuService(session=session, menu_repo=menu_repo)


@router.get(
    "/branches/{branch_id}/menu",
    response_model=MenuResponse,
    status_code=status.HTTP_200_OK,
    summary="Get branch menu catalog",
    description="Public endpoint returning full active menu hierarchy for a branch.",
)
async def get_branch_menu(
    branch_id: uuid.UUID,
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.get_branch_menu(branch_id)


@router.post(
    "/branches/{branch_id}/menus",
    response_model=MenuResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create branch menu",
    description="Creates a main menu for a branch.",
)
async def create_branch_menu(
    branch_id: uuid.UUID,
    req: MenuCreate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await menu_service.create_branch_menu(branch_id, req)


@router.patch("/menus/{menu_id}", response_model=MenuResponse)
async def update_menu(
    menu_id: uuid.UUID,
    req: MenuUpdate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> Menu:
    menu = await session.scalar(
        select(Menu)
        .where(Menu.id == menu_id, Menu.deleted_at.is_(None))
        .options(
            selectinload(Menu.categories)
            .selectinload(MenuCategory.items)
            .selectinload(MenuItem.modifiers)
        )
    )
    if not menu or menu.deleted_at is not None:
        raise EntityNotFoundError("Menu not found.", "MENU_NOT_FOUND")
    await require_branch_access(session, current_user.sub, current_user.role, menu.branch_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(menu, field, value)
    await session.commit()
    await session.refresh(menu)
    return menu


@router.post(
    "/branches/{branch_id}/menu/categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create menu category",
    description="Creates a new menu category within a branch menu.",
)
async def create_category(
    branch_id: uuid.UUID,
    req: MenuCategoryCreate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await menu_service.create_category(branch_id, req)


@router.get("/menu/categories/{category_id}", response_model=MenuCategoryResponse)
async def get_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MenuCategory:
    category = await session.scalar(
        select(MenuCategory)
        .where(MenuCategory.id == category_id, MenuCategory.deleted_at.is_(None))
        .options(selectinload(MenuCategory.items).selectinload(MenuItem.modifiers))
    )
    if not category or category.deleted_at is not None:
        raise EntityNotFoundError("Category not found.", "CATEGORY_NOT_FOUND")
    return category


@router.patch("/menu/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    req: MenuCategoryUpdate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> MenuCategory:
    category = await session.scalar(
        select(MenuCategory)
        .where(MenuCategory.id == category_id, MenuCategory.deleted_at.is_(None))
        .options(selectinload(MenuCategory.items).selectinload(MenuItem.modifiers))
    )
    if not category or category.deleted_at is not None:
        raise EntityNotFoundError("Category not found.", "CATEGORY_NOT_FOUND")
    menu = await session.get(Menu, category.menu_id)
    await require_branch_access(session, current_user.sub, current_user.role, menu.branch_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/menu/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    category = await session.get(MenuCategory, category_id)
    if not category or category.deleted_at is not None:
        raise EntityNotFoundError("Category not found.", "CATEGORY_NOT_FOUND")
    menu = await session.get(Menu, category.menu_id)
    await require_branch_access(session, current_user.sub, current_user.role, menu.branch_id)
    category.soft_delete()
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/branches/{branch_id}/menu/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create menu item",
    description="Adds a dish/item to a branch menu category. Requires base_price >= 0.00.",
)
async def create_menu_item(
    branch_id: uuid.UUID,
    req: MenuItemCreate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await menu_service.create_menu_item(branch_id, req)


@router.get(
    "/menu/items/{item_id}",
    response_model=MenuItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get menu item details",
    description="Fetches a specific menu item by ID.",
)
async def get_menu_item(
    item_id: uuid.UUID,
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.get_menu_item(item_id)


@router.patch(
    "/menu/items/{item_id}",
    response_model=MenuItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update menu item",
    description="Updates item metadata or availability. Enforces base_price >= 0.00 invariant.",
)
async def update_menu_item(
    item_id: uuid.UUID,
    req: MenuItemUpdate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    _, branch_id = await _item_branch(session, item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    return await menu_service.update_menu_item(item_id, req)


@router.patch("/menu/items/{item_id}/availability", response_model=MenuItemResponse)
async def toggle_menu_item(
    item_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> MenuItem:
    item, branch_id = await _item_branch(session, item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    item.is_available = not item.is_available
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/menu/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    item_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    item, branch_id = await _item_branch(session, item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    item.soft_delete()
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/menu/items/{item_id}/modifiers", response_model=MenuModifierResponse, status_code=201
)
async def create_modifier(
    item_id: uuid.UUID,
    req: MenuModifierCreate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> MenuModifier:
    _, branch_id = await _item_branch(session, item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    modifier = MenuModifier(menu_item_id=item_id, **req.model_dump())
    session.add(modifier)
    await session.commit()
    await session.refresh(modifier)
    return modifier


@router.patch("/menu/modifiers/{modifier_id}", response_model=MenuModifierResponse)
async def update_modifier(
    modifier_id: uuid.UUID,
    req: MenuModifierUpdate,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> MenuModifier:
    modifier = await session.get(MenuModifier, modifier_id)
    if not modifier:
        raise EntityNotFoundError("Modifier not found.", "MODIFIER_NOT_FOUND")
    _, branch_id = await _item_branch(session, modifier.menu_item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(modifier, field, value)
    await session.commit()
    await session.refresh(modifier)
    return modifier


@router.get("/menu/modifiers/{modifier_id}", response_model=MenuModifierResponse)
async def get_modifier(
    modifier_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MenuModifier:
    modifier = await session.get(MenuModifier, modifier_id)
    if not modifier:
        raise EntityNotFoundError("Modifier not found.", "MODIFIER_NOT_FOUND")
    return modifier


@router.delete("/menu/modifiers/{modifier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modifier(
    modifier_id: uuid.UUID,
    current_user: UserClaims = Depends(require_role(CATALOG_ROLES)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    modifier = await session.get(MenuModifier, modifier_id)
    if not modifier:
        raise EntityNotFoundError("Modifier not found.", "MODIFIER_NOT_FOUND")
    _, branch_id = await _item_branch(session, modifier.menu_item_id)
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    await session.delete(modifier)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
