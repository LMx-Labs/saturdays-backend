import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.customer.repository import CustomerRepository
from app.garba.schemas import (
    GarbaAvailabilityResponse,
    GarbaBookingCreateRequest,
    GarbaBookingCreateResponse,
    GarbaBookingResponse,
    GarbaInventoryCell,
    GarbaInventoryUpdate,
    GarbaScanRequest,
    GarbaScanResponse,
    GarbaVerifyRequest,
)
from app.garba.service import GarbaService

router = APIRouter(prefix="/events/garba", tags=["Garba"])


def get_garba_service(
    session: AsyncSession = Depends(get_db_session),
) -> GarbaService:
    return GarbaService(session=session)


async def _customer_profile_id(
    current_user: UserClaims, session: AsyncSession
) -> uuid.UUID:
    profile = await CustomerRepository(session).get_by_user_id(
        uuid.UUID(current_user.sub)
    )
    if not profile:
        raise EntityNotFoundError("Customer profile not found.", "CUSTOMER_NOT_FOUND")
    return profile.id


@router.get(
    "/availability",
    response_model=GarbaAvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Garba Night seats remaining",
)
async def garba_availability(
    service: GarbaService = Depends(get_garba_service),
) -> GarbaAvailabilityResponse:
    return await service.availability()


@router.get(
    "/admin/inventory",
    response_model=list[GarbaInventoryCell],
    summary="Garba seat caps, sales, and holds",
)
async def garba_inventory(
    _admin: UserClaims = Depends(require_role(["Admin"])),
    service: GarbaService = Depends(get_garba_service),
) -> list[GarbaInventoryCell]:
    return await service.inventory()


@router.patch(
    "/admin/inventory",
    response_model=GarbaInventoryCell,
    summary="Change the seat cap for one category and date",
)
async def update_garba_inventory(
    req: GarbaInventoryUpdate,
    _admin: UserClaims = Depends(require_role(["Admin"])),
    service: GarbaService = Depends(get_garba_service),
) -> GarbaInventoryCell:
    return await service.set_capacity(req)


@router.post(
    "/admin/scan",
    response_model=GarbaScanResponse,
    summary="Scan a ticket QR code and admit the attendee",
)
async def scan_garba_ticket(
    req: GarbaScanRequest,
    admin: UserClaims = Depends(require_role(["Admin"])),
    service: GarbaService = Depends(get_garba_service),
) -> GarbaScanResponse:
    return await service.scan(req.code, admin.sub)


@router.post(
    "/bookings",
    response_model=GarbaBookingCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Hold Garba seats and create a Razorpay order",
)
async def create_garba_booking(
    req: GarbaBookingCreateRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: GarbaService = Depends(get_garba_service),
) -> GarbaBookingCreateResponse:
    customer_profile_id = await _customer_profile_id(current_user, session)
    return await service.create_booking(customer_profile_id, req)


@router.get(
    "/bookings/me",
    response_model=list[GarbaBookingResponse],
    status_code=status.HTTP_200_OK,
    summary="Paid Garba tickets for the current customer",
)
async def my_garba_bookings(
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: GarbaService = Depends(get_garba_service),
) -> list[GarbaBookingResponse]:
    customer_profile_id = await _customer_profile_id(current_user, session)
    return await service.list_paid(customer_profile_id)


@router.post(
    "/bookings/{booking_id}/verify",
    response_model=GarbaBookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Garba payment and issue ticket numbers",
)
async def verify_garba_booking(
    booking_id: uuid.UUID,
    req: GarbaVerifyRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    service: GarbaService = Depends(get_garba_service),
) -> GarbaBookingResponse:
    customer_profile_id = await _customer_profile_id(current_user, session)
    return await service.verify_payment(booking_id, customer_profile_id, req)
