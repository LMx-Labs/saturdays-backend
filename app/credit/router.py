import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditLog
from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.credit.schemas import (
    StoreCreditBalanceResponse,
    StoreCreditGrantRequest,
    StoreCreditResponse,
)
from app.credit.service import StoreCreditService
from app.customer.repository import CustomerRepository

router = APIRouter(prefix="/store-credits", tags=["Store Credit"])


async def _profile_id(session: AsyncSession, user: UserClaims) -> uuid.UUID:
    profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(user.sub))
    if not profile:
        raise EntityNotFoundError("Customer profile not found.", "CUSTOMER_NOT_FOUND")
    return profile.id


@router.get(
    "",
    response_model=list[StoreCreditResponse],
    summary="List my store credits",
)
async def list_my_store_credits(
    current_user: UserClaims = Depends(require_role(["Customer"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoreCreditResponse]:
    credits = await StoreCreditService(session).list_credits(
        await _profile_id(session, current_user)
    )
    return [StoreCreditResponse.model_validate(c) for c in credits]


@router.get(
    "/balance",
    response_model=StoreCreditBalanceResponse,
    summary="Spendable store credit balance at a brand",
)
async def get_my_balance(
    brand_id: uuid.UUID = Query(...),
    current_user: UserClaims = Depends(require_role(["Customer"])),
    session: AsyncSession = Depends(get_db_session),
) -> StoreCreditBalanceResponse:
    balance = await StoreCreditService(session).get_balance(
        await _profile_id(session, current_user), brand_id
    )
    return StoreCreditBalanceResponse(brand_id=brand_id, available_balance=balance)


@router.post(
    "/grant",
    response_model=StoreCreditResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant store credit manually (PlatformAdmin)",
)
async def grant_store_credit(
    req: StoreCreditGrantRequest,
    request: Request,
    admin: UserClaims = Depends(require_role(["PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
) -> StoreCreditResponse:
    credit = await StoreCreditService(session).issue(
        customer_profile_id=req.customer_profile_id,
        brand_id=req.brand_id,
        amount=req.amount,
        reason=req.reason,
    )
    session.add(
        AdminAuditLog(
            admin_user_id=uuid.UUID(admin.sub),
            action="STORE_CREDIT_GRANTED",
            target_entity="store_credits",
            target_entity_id=credit.id,
            changes_payload=req.model_dump(mode="json"),
            ip_address=request.client.host if request.client else "127.0.0.1",
        )
    )
    await session.commit()
    return StoreCreditResponse.model_validate(credit)
