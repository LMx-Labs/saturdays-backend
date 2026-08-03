import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.customer.repository import CustomerRepository, CustomerRepositoryInterface
from app.customer.schemas import (
    CustomerAddressCreate,
    CustomerAddressResponse,
    CustomerFavoriteCreate,
    CustomerFavoriteResponse,
    CustomerProfileResponse,
    CustomerProfileUpdate,
)
from app.customer.service import CustomerService, CustomerServiceInterface

router = APIRouter(prefix="/customers", tags=["Customer"])


def get_customer_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CustomerRepositoryInterface:
    return CustomerRepository(session=session)


def get_customer_service(
    session: AsyncSession = Depends(get_db_session),
    customer_repo: CustomerRepositoryInterface = Depends(get_customer_repository),
) -> CustomerServiceInterface:
    return CustomerService(session=session, customer_repo=customer_repo)


@router.get(
    "/me",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer profile",
)
async def get_my_profile(
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> CustomerProfileResponse:
    return await customer_service.get_or_create_profile(
        user_id=uuid.UUID(current_user.sub), default_name="Customer"
    )


@router.put(
    "/me",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update customer profile",
)
async def update_my_profile(
    req: CustomerProfileUpdate,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> CustomerProfileResponse:
    return await customer_service.update_profile(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.get(
    "/me/addresses",
    response_model=list[CustomerAddressResponse],
    status_code=status.HTTP_200_OK,
    summary="List customer delivery addresses",
)
async def list_addresses(
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> list[CustomerAddressResponse]:
    return await customer_service.get_addresses(user_id=uuid.UUID(current_user.sub))


@router.post(
    "/me/addresses",
    response_model=CustomerAddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add customer delivery address",
)
async def add_address(
    req: CustomerAddressCreate,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> CustomerAddressResponse:
    return await customer_service.add_address(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.put(
    "/me/addresses/{address_id}/primary",
    response_model=CustomerAddressResponse,
    status_code=status.HTTP_200_OK,
    summary="Set primary delivery address",
)
async def set_primary_address(
    address_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> CustomerAddressResponse:
    return await customer_service.set_primary_address(
        user_id=uuid.UUID(current_user.sub), address_id=address_id
    )


@router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer delivery address",
)
async def delete_address(
    address_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> None:
    await customer_service.delete_address(
        user_id=uuid.UUID(current_user.sub), address_id=address_id
    )


@router.get(
    "/me/favorites",
    response_model=list[CustomerFavoriteResponse],
    status_code=status.HTTP_200_OK,
    summary="List customer favorite store bookmarks",
)
async def list_favorites(
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> list[CustomerFavoriteResponse]:
    return await customer_service.get_favorites(user_id=uuid.UUID(current_user.sub))


@router.post(
    "/me/favorites",
    response_model=CustomerFavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add branch to customer favorites",
)
async def add_favorite(
    req: CustomerFavoriteCreate,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> CustomerFavoriteResponse:
    return await customer_service.add_favorite(
        user_id=uuid.UUID(current_user.sub), branch_id=req.branch_id
    )


@router.delete(
    "/me/favorites/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove branch from customer favorites",
)
async def remove_favorite(
    branch_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    customer_service: CustomerServiceInterface = Depends(get_customer_service),
) -> None:
    await customer_service.remove_favorite(
        user_id=uuid.UUID(current_user.sub), branch_id=branch_id
    )
