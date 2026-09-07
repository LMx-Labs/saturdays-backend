import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.authorization import require_branch_access
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.inventory.models import InventoryItem, InventoryLog
from app.inventory.repository import (
    InventoryRepository,
    InventoryRepositoryInterface,
)
from app.inventory.schemas import (
    InventoryItemCreateRequest,
    InventoryItemDetailResponse,
    InventoryItemResponse,
    InventoryLogPage,
    InventoryLogResponse,
    StockUpdateRequest,
)
from app.inventory.service import (
    InventoryService,
    InventoryServiceInterface,
)
from app.menu.models import MenuItem

router = APIRouter(prefix="", tags=["Inventory"])


def get_inventory_repository(
    session: AsyncSession = Depends(get_db_session),
) -> InventoryRepositoryInterface:
    return InventoryRepository(session=session)


def get_inventory_service(
    session: AsyncSession = Depends(get_db_session),
    inventory_repo: InventoryRepositoryInterface = Depends(get_inventory_repository),
) -> InventoryServiceInterface:
    return InventoryService(session=session, inventory_repo=inventory_repo)


@router.get(
    "/branches/{branch_id}/inventory",
    response_model=list[InventoryItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get branch stock inventory",
    description="Retrieves stock counts and availability flags for all menu items at a branch.",
)
async def get_branch_inventory(
    branch_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> list[InventoryItemResponse]:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    items = await inventory_service.get_branch_inventory(branch_id)
    return [InventoryItemResponse.model_validate(item) for item in items]


@router.get(
    "/branches/{branch_id}/inventory/details",
    response_model=list[InventoryItemDetailResponse],
)
async def get_branch_inventory_details(
    branch_id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> list[InventoryItemDetailResponse]:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    result = await session.execute(
        select(InventoryItem)
        .where(InventoryItem.branch_id == branch_id, InventoryItem.deleted_at.is_(None))
        .options(
            selectinload(InventoryItem.menu_item).selectinload(MenuItem.modifiers)
        )
        .order_by(InventoryItem.created_at.desc())
    )
    return [InventoryItemDetailResponse.model_validate(item) for item in result.scalars()]


@router.get("/inventory/{id}", response_model=InventoryItemDetailResponse)
async def get_inventory_item(
    id: uuid.UUID,
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> InventoryItemDetailResponse:
    item = await session.scalar(
        select(InventoryItem)
        .where(InventoryItem.id == id, InventoryItem.deleted_at.is_(None))
        .options(
            selectinload(InventoryItem.menu_item).selectinload(MenuItem.modifiers)
        )
    )
    if not item:
        raise EntityNotFoundError("Inventory item not found.", "INVENTORY_ITEM_NOT_FOUND")
    await require_branch_access(session, current_user.sub, current_user.role, item.branch_id)
    return InventoryItemDetailResponse.model_validate(item)


@router.get("/inventory/{id}/logs", response_model=InventoryLogPage)
async def get_inventory_logs(
    id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
) -> InventoryLogPage:
    item = await session.get(InventoryItem, id)
    if not item or item.deleted_at is not None:
        raise EntityNotFoundError("Inventory item not found.", "INVENTORY_ITEM_NOT_FOUND")
    await require_branch_access(session, current_user.sub, current_user.role, item.branch_id)
    total = (
        await session.scalar(
            select(func.count(InventoryLog.id)).where(InventoryLog.inventory_item_id == id)
        )
        or 0
    )
    logs = (
        (
            await session.execute(
                select(InventoryLog)
                .where(InventoryLog.inventory_item_id == id)
                .order_by(InventoryLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return InventoryLogPage(
        items=[InventoryLogResponse.model_validate(log) for log in logs],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "/branches/{branch_id}/inventory",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or initialize item stock",
    description="Initializes stock record for a dish in a branch inventory.",
)
async def create_inventory_item(
    branch_id: uuid.UUID,
    req: InventoryItemCreateRequest,
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> InventoryItemResponse:
    await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    item = await inventory_service.create_inventory_item(branch_id, req)
    return InventoryItemResponse.model_validate(item)


@router.patch(
    "/inventory/{id}/stock",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update stock quantity and availability",
    description="Exclusive DineGuru route to update item stock quantity or toggle stock status.",
)
async def update_stock(
    id: uuid.UUID,
    req: StockUpdateRequest,
    current_user: UserClaims = Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "PlatformAdmin"])
    ),
    session: AsyncSession = Depends(get_db_session),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> InventoryItemResponse:
    inventory_item = await session.get(InventoryItem, id)
    if not inventory_item or inventory_item.deleted_at is not None:
        raise EntityNotFoundError(
            message="Inventory item not found.", error_code="INVENTORY_ITEM_NOT_FOUND"
        )
    await require_branch_access(
        session, current_user.sub, current_user.role, inventory_item.branch_id
    )
    item = await inventory_service.update_stock(id, req)
    return InventoryItemResponse.model_validate(item)
