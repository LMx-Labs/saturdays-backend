import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.core.database import get_db_session
from app.menu.repository import MenuRepository, MenuRepositoryInterface
from app.menu.schemas import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuCreate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MenuResponse,
)
from app.menu.service import MenuService, MenuServiceInterface

router = APIRouter(prefix="", tags=["Menu"])


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
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.create_branch_menu(branch_id, req)


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
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.create_category(branch_id, req)


@router.patch(
    "/menu/categories/{category_id}",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update menu category",
    description="Update a category's name and/or display order.",
)
async def update_category(
    category_id: uuid.UUID,
    req: MenuCategoryUpdate,
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.update_category(category_id, req)


@router.delete(
    "/menu/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete menu category",
    description="Delete an empty category or soft-delete it after reassigning dishes to a fallback category.",
)
async def delete_category(
    category_id: uuid.UUID,
    fallback_category_id: uuid.UUID | None = Query(
        default=None,
        description="Optional fallback category ID to reassign dishes before deleting.",
    ),
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> None:
    await menu_service.delete_category(category_id, fallback_category_id)


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
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
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
    _current_user=Depends(
        require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    menu_service: MenuServiceInterface = Depends(get_menu_service),
) -> Any:
    return await menu_service.update_menu_item(item_id, req)
