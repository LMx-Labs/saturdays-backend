import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserClaims
from app.core.authorization import require_role
from app.core.database import get_db_session
from app.core.roles import Role
from app.merchant.staff_schemas import (
    StaffInvitationResponse,
    StaffInviteRequest,
    StaffResponse,
    StaffUpdateRequest,
)
from app.merchant.staff_service import MerchantStaffService

router = APIRouter(prefix="/merchants/staff", tags=["Merchant Staff"])


def get_service(
    session: AsyncSession = Depends(get_db_session),
) -> MerchantStaffService:
    return MerchantStaffService(session)


@router.get("", response_model=list[StaffResponse])
async def list_staff(
    current: UserClaims = Depends(require_role([Role.MERCHANT_OWNER.value])),
    service: MerchantStaffService = Depends(get_service),
) -> list[StaffResponse]:
    return await service.list_staff(uuid.UUID(current.sub))


@router.post(
    "/invitations",
    response_model=StaffInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_staff(
    req: StaffInviteRequest,
    current: UserClaims = Depends(require_role([Role.MERCHANT_OWNER.value])),
    service: MerchantStaffService = Depends(get_service),
) -> StaffInvitationResponse:
    return await service.invite(uuid.UUID(current.sub), req)


@router.patch("/{membership_id}", response_model=StaffResponse)
async def update_staff(
    membership_id: uuid.UUID,
    req: StaffUpdateRequest,
    current: UserClaims = Depends(require_role([Role.MERCHANT_OWNER.value])),
    service: MerchantStaffService = Depends(get_service),
) -> StaffResponse:
    return await service.update_staff(uuid.UUID(current.sub), membership_id, req)


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    membership_id: uuid.UUID,
    current: UserClaims = Depends(require_role([Role.MERCHANT_OWNER.value])),
    service: MerchantStaffService = Depends(get_service),
) -> None:
    await service.remove_staff(uuid.UUID(current.sub), membership_id)
