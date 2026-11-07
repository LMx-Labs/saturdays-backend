"""Which orders a restaurant is allowed to know about.

An order exists from the moment a student starts to pay, but it only becomes the restaurant's
order once the payment is confirmed. So the restaurant must never see an order that is still
waiting for payment, and also not one that was cancelled (by the student, or by expiry) while it
was still waiting: that order never reached them either. Seeing it later as "cancelled" in their
history or their counts would be as wrong as seeing it live.

This looks at the order's own history, not at a special "abandoned" status, because apps that
have not been updated yet read an unknown status as "placed".
"""

from sqlalchemy import ColumnElement, exists, or_

from app.order.models import Order, OrderStatusLog

PENDING_PAYMENT = "PENDING_PAYMENT"


def never_placed() -> ColumnElement[bool]:
    """SQL: the order was never paid for, so it never became a restaurant's order."""
    cancelled_while_unpaid = exists().where(
        OrderStatusLog.order_id == Order.id,
        OrderStatusLog.previous_status == PENDING_PAYMENT,
        OrderStatusLog.new_status == "CANCELLED",
    )
    return or_(Order.status == PENDING_PAYMENT, cancelled_while_unpaid)


def was_never_placed(order: Order) -> bool:
    """The same question for an order already loaded with its status history."""
    if order.status == PENDING_PAYMENT:
        return True
    return any(
        log.previous_status == PENDING_PAYMENT and log.new_status == "CANCELLED"
        for log in order.status_logs
    )
