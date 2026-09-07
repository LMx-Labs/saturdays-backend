import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.router import get_current_user, require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.core.authorization import require_branch_access
from app.core.exceptions import EntityNotFoundError, ForbiddenError
from app.customer.repository import CustomerRepository
from app.order.models import Order
from app.payment.models import Payment
from app.payment.repository import PaymentRepository, PaymentRepositoryInterface
from app.payment.schemas import (
    PaymentIntentCreateRequest,
    PaymentIntentResponse,
    MockPaymentCompleteRequest,
    PaymentPage,
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
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentVerifyResponse:
    profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
    if current_user.role != "Customer" or not profile:
        raise ForbiddenError("Only the owning customer can verify payment.")
    return await payment_service.verify_payment(req, profile.id)


@router.post(
    "/mock/complete",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete deterministic local mock payment",
)
async def complete_mock_payment(
    req: MockPaymentCompleteRequest,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentVerifyResponse:
    if current_user.role != "Customer":
        raise ForbiddenError("Only customers can complete mock payments.")
    profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
    if not profile:
        raise EntityNotFoundError("Customer profile not found.", "CUSTOMER_NOT_FOUND")
    return await payment_service.complete_mock_payment(req.order_id, profile.id)


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
    current_user=Depends(require_role(["BranchManager", "MerchantOwner", "PlatformAdmin"])),
    session: AsyncSession = Depends(get_db_session),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentTransactionResponse:
    payment = await payment_service.get_payment_history(id)
    order = await session.get(Order, payment.order_id)
    if not order:
        raise EntityNotFoundError("Order not found.", "ORDER_NOT_FOUND")
    await require_branch_access(session, current_user.sub, current_user.role, order.branch_id)
    tx = await payment_service.refund_payment(id, req)
    return PaymentTransactionResponse.model_validate(tx)


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    branch_id: uuid.UUID | None = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentResponse]:
    stmt = select(Payment).options(selectinload(Payment.transactions))
    if current_user.role == "Customer":
        profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
        if not profile:
            return []
        stmt = stmt.where(Payment.customer_profile_id == profile.id)
    elif current_user.role != "PlatformAdmin":
        if not branch_id:
            raise ForbiddenError("branch_id is required.", "BRANCH_ID_REQUIRED")
        await require_branch_access(session, current_user.sub, current_user.role, branch_id)
        stmt = stmt.join(Order, Order.id == Payment.order_id).where(Order.branch_id == branch_id)
    elif branch_id:
        stmt = stmt.join(Order, Order.id == Payment.order_id).where(Order.branch_id == branch_id)
    payments = (await session.execute(stmt.order_by(Payment.created_at.desc()))).scalars()
    return [PaymentResponse.model_validate(payment) for payment in payments]


@router.get("/history", response_model=PaymentPage)
async def get_payment_history_page(
    branch_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentPage:
    filters = []
    join_order = branch_id is not None
    if current_user.role == "Customer":
        profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
        if not profile:
            return PaymentPage(items=[], page=page, page_size=page_size, total=0, pages=0)
        filters.append(Payment.customer_profile_id == profile.id)
        join_order = False
    elif current_user.role != "PlatformAdmin":
        if branch_id is None:
            raise ForbiddenError("branch_id is required.", "BRANCH_ID_REQUIRED")
        await require_branch_access(session, current_user.sub, current_user.role, branch_id)
    base = select(Payment)
    count_stmt = select(func.count(Payment.id))
    if join_order:
        base = base.join(Order, Order.id == Payment.order_id)
        count_stmt = count_stmt.join(Order, Order.id == Payment.order_id)
        filters.append(Order.branch_id == branch_id)
    total = await session.scalar(count_stmt.where(*filters)) or 0
    payments = (
        (
            await session.execute(
                base.where(*filters)
                .options(selectinload(Payment.transactions))
                .order_by(Payment.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return PaymentPage(
        items=[PaymentResponse.model_validate(payment) for payment in payments],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/order/{order_id}", response_model=PaymentResponse)
async def get_payment_by_order(
    order_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentResponse:
    payment = await PaymentRepository(session).get_by_order_id(order_id)
    if not payment:
        raise EntityNotFoundError("Payment not found.", "PAYMENT_NOT_FOUND")
    order = await session.get(Order, order_id)
    if not order:
        raise EntityNotFoundError("Order not found.", "ORDER_NOT_FOUND")
    if current_user.role == "Customer":
        profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
        if not profile or profile.id != payment.customer_profile_id:
            raise ForbiddenError("Payment access denied.", "PAYMENT_ACCESS_FORBIDDEN")
    else:
        await require_branch_access(session, current_user.sub, current_user.role, order.branch_id)
    return PaymentResponse.model_validate(payment)


@router.get(
    "/{id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment transaction history",
    description="Retrieves payment details and full append-only transaction history log.",
)
async def get_payment(
    id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    payment_service: PaymentServiceInterface = Depends(get_payment_service),
) -> PaymentResponse:
    payment = await payment_service.get_payment_history(id)
    if current_user.role == "Customer":
        profile = await CustomerRepository(session).get_by_user_id(uuid.UUID(current_user.sub))
        if not profile or profile.id != payment.customer_profile_id:
            raise ForbiddenError("Payment access denied.", "PAYMENT_ACCESS_FORBIDDEN")
    else:
        order = await session.get(Order, payment.order_id)
        if not order:
            raise EntityNotFoundError("Order not found.", "ORDER_NOT_FOUND")
        await require_branch_access(session, current_user.sub, current_user.role, order.branch_id)
    return PaymentResponse.model_validate(payment)
