import uuid

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    WebSocket,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_branch_access
from app.auth.router import get_current_user, require_role
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

router = APIRouter(prefix="", tags=["Order"])

STAFF_ROLES = {
    "KitchenStaff",
    "BranchManager",
    "MerchantOwner",
    "PlatformAdmin",
}


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
    idempotency_key: str = Header(
        ..., min_length=8, max_length=128, alias="Idempotency-Key"
    ),
    current_user: UserClaims = Depends(require_role(["Customer"])),
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
        idempotency_key=idempotency_key,
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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> list[OrderResponse]:
    if branch_id and current_user.role in STAFF_ROLES:
        await require_branch_access(session, current_user, branch_id)
        orders = await order_service.get_branch_orders(
            branch_id, status=order_status, skip=skip, limit=limit
        )
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
        await require_branch_access(session, current_user, order.branch_id)
    else:
        raise ForbiddenError("Order access denied.", "ORDER_ACCESS_FORBIDDEN")
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
        await require_branch_access(session, current_user, existing.branch_id)
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
        actor_role=current_user.role,
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
        await require_branch_access(session, current_user, existing.branch_id)
    else:
        raise ForbiddenError(
            message="You do not have access to this order.",
            error_code="ORDER_ACCESS_FORBIDDEN",
        )
    order = await order_service.cancel_order(
        order_id=id,
        user_id=uuid.UUID(current_user.sub),
        actor_role=current_user.role,
    )
    return OrderResponse.model_validate(order)


@router.websocket("/ws/branches/{branch_id}/orders")
async def websocket_branch_orders(
    websocket: WebSocket,
    branch_id: uuid.UUID,
):
    """Closed until authenticated, branch-scoped WebSocket sessions are supported."""
    await websocket.close(code=1008)
