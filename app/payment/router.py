import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError
from app.customer.repository import CustomerRepository
from app.payment.repository import PaymentRepository, PaymentRepositoryInterface
from app.payment.schemas import (
    PaymentIntentCreateRequest,
    PaymentIntentResponse,
    PaymentResponse,
    PaymentTransactionResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    RefundCreateRequest,
)
from app.payment.service import PaymentService, PaymentServiceInterface

router = APIRouter(prefix="/payments", tags=["Payment"])


def get_payment_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PaymentRepositoryInterface:
    return PaymentRepository(session=session)


def get_payment_service(
    session: AsyncSession = Depends(get_db_session),
    payment_repo: PaymentRepositoryInterface = Depends(get_payment_repository),
) -> PaymentServiceInterface:
    return PaymentService(session=session, payment_repo=payment_repo)


@router.post(
    "/intent",
    response_model=PaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment intent",
    description="Initiates a Razorpay payment order intent for checkout.",
)
async def create_payment_intent(
    req: PaymentIntentCreateRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentIntentResponse:
    cust_repo = CustomerRepository(session)
    profile = await cust_repo.get_by_user_id(uuid.UUID(current_user.sub))
    if not profile:
        raise EntityNotFoundError("Customer profile not found.", "CUSTOMER_NOT_FOUND")

    return await payment_service.create_payment_intent(
        customer_profile_id=profile.id,
        order_id=req.order_id,
        amount=req.amount,
        currency=req.currency,
    )


@router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify payment signature",
    description="Verifies Razorpay HMAC signature and appends VERIFIED and CAPTURED transaction records.",
)
async def verify_payment(
    req: PaymentVerifyRequest,
    _current_user: UserClaims = Depends(get_current_user),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentVerifyResponse:
    return await payment_service.verify_payment(req)


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook callback",
    description="Processes asynchronous Razorpay webhook events with HMAC signature validation.",
)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature"),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> dict[str, Any]:
    raw_body = await request.body()
    return await payment_service.process_webhook(raw_body, x_razorpay_signature)


@router.post(
    "/{id}/refund",
    response_model=PaymentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue refund",
    description="Issues full or partial refund. Enforces INV-PAY-001 refund cap.",
)
async def refund_payment(
    id: uuid.UUID,
    req: RefundCreateRequest,
    _current_user=Depends(require_role(["BranchManager", "MerchantOwner", "Admin"])),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentTransactionResponse:
    tx = await payment_service.refund_payment(id, req)
    return PaymentTransactionResponse.model_validate(tx)


@router.get(
    "/{id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment transaction history",
    description="Retrieves payment details and full append-only transaction history log.",
)
async def get_payment(
    id: uuid.UUID,
    _current_user: UserClaims = Depends(get_current_user),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await payment_service.get_payment_history(id)
    return PaymentResponse.model_validate(payment)
