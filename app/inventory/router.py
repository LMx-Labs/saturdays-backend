import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.core.database import get_db_session
from app.inventory.repository import (
    InventoryRepository,
    InventoryRepositoryInterface,
)
from app.inventory.schemas import (
    InventoryItemCreateRequest,
    InventoryItemResponse,
    StockUpdateRequest,
)
from app.inventory.service import (
    InventoryService,
    InventoryServiceInterface,
)

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
    _current_user=Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "Admin"])
    ),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> list[InventoryItemResponse]:
    items = await inventory_service.get_branch_inventory(branch_id)
    return [InventoryItemResponse.model_validate(item) for item in items]


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
    _current_user=Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "Admin"])
    ),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> InventoryItemResponse:
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
    _current_user=Depends(
        require_role(["KitchenStaff", "BranchManager", "MerchantOwner", "Admin"])
    ),
    inventory_service: InventoryServiceInterface = Depends(get_inventory_service),
) -> InventoryItemResponse:
    item = await inventory_service.update_stock(id, req)
    return InventoryItemResponse.model_validate(item)
