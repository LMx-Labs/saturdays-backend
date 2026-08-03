import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.cart.repository import CartRepository, CartRepositoryInterface
from app.cart.schemas import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartResponse,
    CartValidationResponse,
)
from app.cart.service import CartService, CartServiceInterface
from app.core.database import get_db_session
from app.customer.repository import CustomerRepository, CustomerRepositoryInterface

router = APIRouter(prefix="/cart", tags=["Cart"])


def get_cart_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CartRepositoryInterface:
    return CartRepository(session=session)


def get_customer_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CustomerRepositoryInterface:
    return CustomerRepository(session=session)


def get_cart_service(
    session: AsyncSession = Depends(get_db_session),
    cart_repo: CartRepositoryInterface = Depends(get_cart_repository),
    customer_repo: CustomerRepositoryInterface = Depends(get_customer_repository),
) -> CartServiceInterface:
    return CartService(
        session=session, cart_repo=cart_repo, customer_repo=customer_repo
    )


@router.get(
    "",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer active shopping cart",
)
async def get_cart(
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.get_cart(user_id=uuid.UUID(current_user.sub))


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Add item to shopping cart",
)
async def add_item(
    req: CartItemAddRequest,
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.add_item(user_id=uuid.UUID(current_user.sub), req=req)


@router.put(
    "/items/{item_id}",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Update cart item quantity",
)
async def update_item_quantity(
    item_id: uuid.UUID,
    req: CartItemUpdateRequest,
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.update_item_quantity(
        user_id=uuid.UUID(current_user.sub), item_id=item_id, req=req
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove item from cart",
)
async def remove_item(
    item_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.remove_item(
        user_id=uuid.UUID(current_user.sub), item_id=item_id
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all items from active cart",
)
async def clear_cart(
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> None:
    await cart_service.clear_cart(user_id=uuid.UUID(current_user.sub))


@router.post(
    "/validate",
    response_model=CartValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate cart items and availability",
)
async def validate_cart(
    current_user: UserClaims = Depends(get_current_user),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> CartValidationResponse:
    return await cart_service.validate_cart(user_id=uuid.UUID(current_user.sub))


@router.delete(
    "/purge-expired",
    status_code=status.HTTP_200_OK,
    summary="Purge abandoned expired carts (>7 days)",
)
async def purge_expired_carts(
    max_age_days: int = Query(7, ge=1, le=30),
    cart_service: CartServiceInterface = Depends(get_cart_service),
) -> dict:
    purged_count = await cart_service.purge_expired_carts(max_age_days=max_age_days)
    return {"purged_count": purged_count, "max_age_days": max_age_days}
