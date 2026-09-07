import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.authorization import require_branch_access
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, ForbiddenError
from app.core.roles import normalize_role
from app.core.security import decode_token
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
    if current_user.role != "Customer":
        raise ForbiddenError("Only customers can create orders.", "ROLE_NOT_AUTHORIZED")
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
        "PlatformAdmin",
    ]:
        await require_branch_access(session, current_user.sub, current_user.role, branch_id)
        orders = await order_service.get_branch_orders(branch_id, status=order_status)
    else:
        if current_user.role != "Customer":
            raise ForbiddenError(
                "A branch_id is required for staff order lists.",
                "BRANCH_ID_REQUIRED",
            )
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
    await _authorize_order_access(session, current_user, order)
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
    order = await order_service.get_order(id)
    if current_user.role not in {
        "KitchenStaff",
        "BranchManager",
        "MerchantOwner",
        "PlatformAdmin",
    }:
        raise ForbiddenError("Customers cannot update order status.", "ROLE_NOT_AUTHORIZED")
    await require_branch_access(session, current_user.sub, current_user.role, order.branch_id)
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
    payload: dict[str, Any] | None = Body(None),
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    order_service: OrderServiceInterface = Depends(get_order_service),
) -> OrderResponse:
    existing = await order_service.get_order(id)
    await _authorize_order_access(session, current_user, existing)
    order = await order_service.cancel_order(
        order_id=id,
        user_id=uuid.UUID(current_user.sub),
        reason=payload.get("reason") if payload else None,
    )
    return OrderResponse.model_validate(order)


@router.websocket("/ws/branches/{branch_id}/orders")
async def websocket_branch_orders(
    websocket: WebSocket,
    branch_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        await authenticate_websocket(websocket, branch_id, session)
    except Exception:
        await websocket.close(code=4403)
        return
    await ws_manager.connect(branch_id, websocket)
    await websocket.send_json(
        {
            "event": "RESYNC_REQUIRED",
            "branch_id": str(branch_id),
            "cursor": datetime.now(UTC).isoformat(),
            "poll_url": f"/api/v1/orders?branch_id={branch_id}",
        }
    )
    try:
        while True:
            # Keep connection alive until client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(branch_id, websocket)


async def _authorize_order_access(session: AsyncSession, current_user: UserClaims, order) -> None:
    if current_user.role == "Customer":
        profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
        if not profile or order.customer_profile_id != profile.id:
            raise ForbiddenError("Order access denied.", "ORDER_ACCESS_FORBIDDEN")
        return
    await require_branch_access(session, current_user.sub, current_user.role, order.branch_id)


async def authenticate_websocket(
    websocket: WebSocket, branch_id: uuid.UUID, session: AsyncSession
) -> UserClaims:
    token = websocket.query_params.get("access_token")
    if not token:
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        parts = [part.strip() for part in protocols.split(",")]
        if len(parts) >= 2 and parts[0].lower() in {"bearer", "access_token"}:
            token = parts[1]
        elif parts and parts[0].lower().startswith("bearer."):
            token = parts[0][7:]
    if not token:
        raise ForbiddenError("WebSocket access token required.", "WS_TOKEN_REQUIRED")
    payload = decode_token(token)
    role = normalize_role(payload.get("role", ""))
    if payload.get("type") != "access" or role not in {
        "KitchenStaff",
        "BranchManager",
        "MerchantOwner",
        "PlatformAdmin",
    }:
        raise ForbiddenError("WebSocket access denied.", "WS_ACCESS_FORBIDDEN")
    claims = UserClaims(sub=payload["sub"], email=payload.get("email", ""), role=role)
    await require_branch_access(session, claims.sub, claims.role, branch_id)
    return claims
