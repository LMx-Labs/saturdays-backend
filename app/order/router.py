import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, ForbiddenError
from app.customer.repository import CustomerRepository
from app.order.repository import OrderRepository, OrderRepositoryInterface
from app.order.schemas import (
    OrderCreateRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.order.service import OrderService, OrderServiceInterface
from app.order.websocket_manager import ws_manager

router = APIRouter(prefix="", tags=["Order"])

STAFF_ROLES = {
    "KitchenStaff",
    "BranchManager",
    "MerchantOwner",
    "PlatformAdmin",
    "Admin",
}


def _assert_staff_branch_access(user: UserClaims, branch_id: uuid.UUID) -> None:
    """Staff bound to a branch (token carries branch_id) may only act on that branch."""
    if (
        user.role in {"KitchenStaff", "BranchManager"}
        and user.branch_id
        and user.branch_id != str(branch_id)
    ):
        raise ForbiddenError(
            message="You can only manage orders of your own branch.",
            error_code="ORDER_BRANCH_FORBIDDEN",
        )


async def _assert_customer_owns_order(
    session: AsyncSession, user: UserClaims, customer_profile_id: uuid.UUID
) -> None:
    profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(user.sub))
    if not profile or profile.id != customer_profile_id:
        raise ForbiddenError(
            message="You do not have access to this order.",
            error_code="ORDER_ACCESS_FORBIDDEN",
        )


def get_order_repository(
    session: AsyncSession = Depends(get_db_session),
) -> OrderRepositoryInterface:
    return OrderRepository(session=session)


def get_order_service(
    session: AsyncSession = Depends(get_db_session),
    order_repo: OrderRepositoryInterface = Depends(get_order_repository),
) -> OrderServiceInterface:
    return OrderService(session=session, order_repo=order_repo)


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer order",
    description="Submits checkout order directly into shared PostgreSQL orders table (ADR-0005).",
)
async def create_order(
    req: OrderCreateRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> OrderResponse:
    cust_repo = CustomerRepository(session)
    profile = await cust_repo.get_by_user_id(uuid.UUID(current_user.sub))
    if not profile:
        raise EntityNotFoundError("Customer profile not found.", "CUSTOMER_NOT_FOUND")

    order = await order_service.create_order(
        user_id=uuid.UUID(current_user.sub),
        customer_profile_id=profile.id,
        req=req,
    )
    return OrderResponse.model_validate(order)


@router.get(
    "/orders",
    response_model=list[OrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List orders",
    description="Lists orders for authenticated customer or for specified branch (Kitchen staff/manager).",
)
async def list_orders(
    branch_id: uuid.UUID | None = Query(None),
    order_status: str | None = Query(None, alias="status"),
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> list[OrderResponse]:
    if branch_id and current_user.role in [
        "KitchenStaff",
        "BranchManager",
        "MerchantOwner",
        "Admin",
    ]:
        _assert_staff_branch_access(current_user, branch_id)
        orders = await order_service.get_branch_orders(branch_id, status=order_status)
    else:
        cust_repo = CustomerRepository(session)
        profile = await cust_repo.get_by_user_id(uuid.UUID(current_user.sub))
        if not profile:
            return []
        orders = await order_service.get_customer_orders(profile.id)

    return [OrderResponse.model_validate(o) for o in orders]


@router.get(
    "/orders/{id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order details",
    description="Fetches single order details with item snapshots and status transition logs.",
)
async def get_order(
    id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> OrderResponse:
    order = await order_service.get_order(id)
    if current_user.role == "Customer":
        await _assert_customer_owns_order(
            session, current_user, order.customer_profile_id
        )
    elif current_user.role in STAFF_ROLES:
        _assert_staff_branch_access(current_user, order.branch_id)
    return OrderResponse.model_validate(order)


@router.patch(
    "/orders/{id}/status",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update order status",
    description="Transitions order status following state machine rules (INV-ORD-002).",
)
async def update_order_status(
    id: uuid.UUID,
    req: OrderStatusUpdateRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> OrderResponse:
    existing = await order_service.get_order(id)
    if current_user.role in STAFF_ROLES:
        _assert_staff_branch_access(current_user, existing.branch_id)
    elif not (req.status == "CANCELLED" and current_user.role == "Customer"):
        # Only staff drive the kitchen workflow (and trigger merchant payouts);
        # customers may only cancel their own order.
        raise ForbiddenError(
            message=f"Role '{current_user.role}' cannot set status '{req.status}'.",
            error_code="ORDER_STATUS_FORBIDDEN",
        )
    if current_user.role == "Customer":
        await _assert_customer_owns_order(
            session, current_user, existing.customer_profile_id
        )
    order = await order_service.update_order_status(
        order_id=id,
        changed_by_user_id=uuid.UUID(current_user.sub),
        target_status=req.status,
    )
    return OrderResponse.model_validate(order)


@router.post(
    "/orders/{id}/cancel",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel order",
    description="Cancels an order if pre-acceptance or via merchant rejection.",
)
async def cancel_order(
    id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> OrderResponse:
    existing = await order_service.get_order(id)
    if current_user.role == "Customer":
        await _assert_customer_owns_order(
            session, current_user, existing.customer_profile_id
        )
    elif current_user.role in STAFF_ROLES:
        _assert_staff_branch_access(current_user, existing.branch_id)
    else:
        raise ForbiddenError(
            message="You do not have access to this order.",
            error_code="ORDER_ACCESS_FORBIDDEN",
        )
    order = await order_service.cancel_order(
        order_id=id,
        user_id=uuid.UUID(current_user.sub),
    )
    return OrderResponse.model_validate(order)


@router.websocket("/ws/branches/{branch_id}/orders")
async def websocket_branch_orders(
    websocket: WebSocket,
    branch_id: uuid.UUID,
):
    """Real-time WebSocket endpoint for DineGuru kitchen terminals (ADR-0010)."""
    await ws_manager.connect(branch_id, websocket)
    try:
        while True:
            # Keep connection alive until client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(branch_id, websocket)
