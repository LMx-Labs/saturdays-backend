"""When an order becomes real: only after it has been paid.

A new order starts as ``PENDING_PAYMENT``. The restaurant cannot see it, so nothing beeps and nobody
cooks food that was never paid for. When the payment is confirmed it becomes ``PLACED`` and only
then do the kitchen screens hear about it. An order that is never paid is cancelled after
``ORDER_PAYMENT_WINDOW_MINUTES`` and the student gets back any store credit they had applied.

Everything here is safe to call more than once and from several requests at the same moment (the
student's own confirmation and Razorpay's webhook usually arrive together): the order row is locked,
so exactly one caller does the placing and the rest see it already done.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.credit.service import StoreCreditService
from app.customer.models import CustomerProfile
from app.order.models import Order, OrderStatusLog
from app.order.repository import OrderRepository
from app.order.websocket_manager import ws_manager
from app.payment.models import Payment, PaymentTransaction

logger = structlog.get_logger()

PENDING_PAYMENT = "PENDING_PAYMENT"

# What place_paid_order reports.
PLACED = "placed"  # this call moved it from waiting-for-payment to placed
ALREADY_PLACED = (
    "already_placed"  # someone else got there first, or it was never waiting
)
CANCELLED_EARLIER = (
    "cancelled"  # it was cancelled (e.g. expired) before the money arrived
)
MISSING = "missing"


async def order_is_paid(session: AsyncSession, order_id: uuid.UUID) -> bool:
    stmt = (
        select(PaymentTransaction.id)
        .join(Payment, Payment.id == PaymentTransaction.payment_id)
        .where(
            Payment.order_id == order_id,
            PaymentTransaction.transaction_type == "CAPTURED",
            PaymentTransaction.status == "SUCCESS",
        )
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def _announce_to_kitchen(order: Order) -> None:
    """Tell the kitchen screens about a paid order. Only ever called for a real, paid order."""
    logger.info(
        "OrderPlacedEvent",
        order_id=str(order.id),
        branch_id=str(order.branch_id),
        customer_profile_id=str(order.customer_profile_id),
        total_amount=float(order.total_amount),
    )
    await ws_manager.broadcast_to_branch(
        branch_id=order.branch_id,
        message={
            "event": "ORDER_PLACED",
            "order_id": str(order.id),
            "total_amount": float(order.total_amount),
            "status": order.status,
        },
    )


async def _move_to_placed(
    session: AsyncSession, order: Order, changed_by_user_id: uuid.UUID
) -> None:
    order.status = "PLACED"
    session.add(
        OrderStatusLog(
            order_id=order.id,
            previous_status=PENDING_PAYMENT,
            new_status="PLACED",
            changed_by_user_id=changed_by_user_id,
        )
    )
    await session.flush()


async def place_paid_order(
    session: AsyncSession, order_id: uuid.UUID, changed_by_user_id: uuid.UUID
) -> str:
    """Make a paid order visible to the restaurant. Idempotent and safe under concurrency."""
    repo = OrderRepository(session)
    order = await repo.get_by_id_for_update(order_id)  # row lock: one caller at a time
    if order is None:
        return MISSING
    if order.status == PENDING_PAYMENT:
        await _move_to_placed(session, order, changed_by_user_id)
        await session.commit()
        await _announce_to_kitchen(order)
        return PLACED
    # Nothing to change. Commit (not roll back) to release the row lock: a rollback would invalidate
    # the objects the calling payment code still holds.
    await session.commit()
    return CANCELLED_EARLIER if order.status == "CANCELLED" else ALREADY_PLACED


def payment_deadline(now: datetime | None = None) -> datetime:
    """Orders created before this moment have waited too long for payment."""
    return (now or datetime.now(UTC)) - timedelta(
        minutes=settings.ORDER_PAYMENT_WINDOW_MINUTES
    )


async def expire_stale_pending_orders(
    session: AsyncSession,
    customer_profile_id: uuid.UUID,
    now: datetime | None = None,
) -> int:
    """Cancel this customer's orders that have waited too long for payment. Returns how many.

    Run when they open their orders or place a new one, so there is no background job to keep alive.
    Cancelling returns any store credit they had applied (the same rule as any cancellation). An
    order that turns out to have been paid after all is placed instead, never cancelled.
    """
    stale_ids = (
        (
            await session.execute(
                select(Order.id).where(
                    Order.customer_profile_id == customer_profile_id,
                    Order.status == PENDING_PAYMENT,
                    Order.created_at < payment_deadline(now),
                )
            )
        )
        .scalars()
        .all()
    )
    if not stale_ids:
        return 0

    profile = await session.get(CustomerProfile, customer_profile_id)
    if profile is None:
        return 0
    repo = OrderRepository(session)
    credit = StoreCreditService(session)
    cancelled = 0
    to_announce: list[Order] = []
    for order_id in stale_ids:
        order = await repo.get_by_id_for_update(order_id)
        if order is None or order.status != PENDING_PAYMENT:
            continue  # someone else dealt with it while we were looking
        if await order_is_paid(session, order.id):
            await _move_to_placed(session, order, profile.user_id)
            to_announce.append(order)
            continue
        order.status = "CANCELLED"
        session.add(
            OrderStatusLog(
                order_id=order.id,
                previous_status=PENDING_PAYMENT,
                new_status="CANCELLED",
                changed_by_user_id=profile.user_id,
            )
        )
        await session.flush()
        await credit.issue_for_cancelled_order(order)
        cancelled += 1
    await session.commit()
    for order in to_announce:
        await _announce_to_kitchen(order)
    if cancelled:
        logger.info(
            "AbandonedOrdersExpired",
            customer_profile_id=str(customer_profile_id),
            count=cancelled,
        )
    return cancelled
