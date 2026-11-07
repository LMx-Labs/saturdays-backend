"""Deciding whether to send a WhatsApp message about an order, and recording that we did.

The rules, in the order they are checked. A message is sent only if ALL of them hold:

  1. WhatsApp is switched on (WHATSAPP_ENABLED) and fully set up.
  2. This event has a template configured (leave a template name empty to switch it off).
  3. The order has actually been paid. Orders exist before payment, so an abandoned
     checkout must never produce a message.
  4. The customer ticked the WhatsApp box and gave a usable number.
  5. While testing, the number is on WHATSAPP_TEST_ALLOWLIST (if one is set).
  6. This message has not already been sent for this order (a database rule guarantees it).

Nothing in here may ever stop an order from being placed, paid or moved along: every problem is
logged and swallowed, and a slow WhatsApp is abandoned after a few seconds.
"""

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.branch.models import Branch
from app.core.config import Settings, settings
from app.core.database import get_db_session
from app.core.uuidv7 import uuid7
from app.customer.models import CustomerProfile
from app.notification.models import Notification
from app.notification.order_code import order_code
from app.notification.phone import mask_phone
from app.notification.whatsapp import (
    TemplateMessage,
    WhatsAppProviderInterface,
    WhatsAppSendError,
    build_whatsapp_provider,
    clean_param,
)
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction

logger = logging.getLogger(__name__)

CAMPUS_TZ = ZoneInfo("Asia/Kolkata")
CHANNEL = "WHATSAPP"

ORDER_CONFIRMED = "order_confirmed"
ORDER_READY = "order_ready"
ORDER_CANCELLED = "order_cancelled"
EVENTS = (ORDER_CONFIRMED, ORDER_READY, ORDER_CANCELLED)

# Which order status change sends which message ("confirmed" is sent when payment is verified).
EVENT_FOR_STATUS = {"READY": ORDER_READY, "CANCELLED": ORDER_CANCELLED}

_TEMPLATE_SETTING = {
    ORDER_CONFIRMED: "WHATSAPP_TEMPLATE_ORDER_CONFIRMED",
    ORDER_READY: "WHATSAPP_TEMPLATE_ORDER_READY",
    ORDER_CANCELLED: "WHATSAPP_TEMPLATE_ORDER_CANCELLED",
}

# The wording to submit to Meta for approval (see WHATSAPP_SETUP.md). It is also what the message
# log shows for each message, so staff can read exactly what a customer was sent. If a template is
# approved with different wording, the log preview is only approximate: the real text is Meta's.
TEMPLATE_TEXT = {
    ORDER_CONFIRMED: (
        "Hi {{1}}, your Saturdays order {{2}} at {{3}} is confirmed ✅\n\n"
        "Pickup: {{4}}\nTotal: ₹{{5}}\n\n"
        "Show your order code at the counter. We'll message you again when it's ready."
    ),
    ORDER_READY: (
        "Good news! Your Saturdays order {{1}} at {{2}} is ready 🎉\n\n"
        "Show your order code at the counter to collect it."
    ),
    ORDER_CANCELLED: (
        "Hi {{1}}, sorry: {{2}} couldn't make your Saturdays order {{3}}, so it has been "
        "cancelled.\n\nWhat you paid has been added to your Saturdays store credit, ready to "
        "use on your next order."
    ),
}


def pickup_phrase(pickup_at: object, now: datetime) -> str:
    """ "today at 1:30 PM", "tomorrow at 1:30 PM", "Tue 11 Nov at 1:30 PM", or a plain fallback."""
    fallback = "as soon as it's ready"
    if not isinstance(pickup_at, str) or not pickup_at:
        return fallback
    try:
        when = datetime.fromisoformat(pickup_at).astimezone(CAMPUS_TZ)
    except ValueError:
        return fallback
    today = now.astimezone(CAMPUS_TZ).date()
    clock = when.strftime("%I:%M %p").lstrip("0")
    days = (when.date() - today).days
    if days == 0:
        return f"today at {clock}"
    if days == 1:
        return f"tomorrow at {clock}"
    return f"{when.strftime('%a')} {when.day} {when.strftime('%b')} at {clock}"


def _money(amount: object) -> str:
    value = float(amount or 0)
    return str(int(value)) if value == int(value) else f"{value:.2f}"


def build_params(
    event: str,
    *,
    customer_name: str,
    code: str,
    branch_name: str,
    pickup_at: object,
    total: object,
    now: datetime,
) -> list[str]:
    first_name = (customer_name or "there").strip().split(" ")[0] or "there"
    if event == ORDER_CONFIRMED:
        return [
            first_name,
            code,
            branch_name,
            pickup_phrase(pickup_at, now),
            _money(total),
        ]
    if event == ORDER_READY:
        return [code, branch_name]
    if event == ORDER_CANCELLED:
        return [first_name, branch_name, code]
    raise ValueError(f"Unknown WhatsApp event {event!r}")


def render_preview(event: str, params: list[str]) -> str:
    text = TEMPLATE_TEXT[event]
    for index, value in enumerate(params, start=1):
        text = text.replace("{{" + str(index) + "}}", clean_param(value))
    return text


def _allowlist(cfg: Settings) -> set[str]:
    return {
        re.sub(r"\D", "", n)
        for n in cfg.WHATSAPP_TEST_ALLOWLIST.split(",")
        if n.strip()
    }


class WhatsAppNotifier:
    def __init__(
        self,
        session: AsyncSession,
        provider: WhatsAppProviderInterface | None = None,
        cfg: Settings | None = None,
    ) -> None:
        self.session = session
        self._provider = provider
        self._cfg = cfg

    @property
    def cfg(self) -> Settings:
        return self._cfg or settings

    async def notify(
        self,
        order_id: uuid.UUID,
        event: str,
        *,
        actor_user_id: uuid.UUID | None = None,
    ) -> bool:
        """Send the message for this event if every rule allows it. Returns True if one was sent.

        Never raises: whatever goes wrong is logged, and the caller carries on.
        """
        try:
            return await self._notify(order_id, event, actor_user_id)
        except Exception:
            # No rollback here on purpose: rolling back expires every object the caller (the
            # order or payment being saved) still holds, which would turn a failed WhatsApp into
            # a failed order. The request's own session handling cleans up at the end.
            logger.exception(
                "WhatsApp: unexpected failure order=%s event=%s", order_id, event
            )
            return False

    async def _claim(self, values: dict) -> bool:
        """Write the log row, unless this message was already recorded for this order.

        "Insert, do nothing if it exists" rather than "insert and catch the error": a caught
        database error needs a rollback, and a rollback would expire the caller's objects.
        Returns True if this call is the one that gets to send the message.
        """
        keys = {
            "index_elements": ["order_id", "channel", "event"],
            "index_where": text("order_id IS NOT NULL"),
        }
        if self.session.get_bind().dialect.name == "postgresql":
            stmt = (
                pg_insert(Notification).values(**values).on_conflict_do_nothing(**keys)
            )
        else:  # SQLite (the test suite)
            stmt = (
                sqlite_insert(Notification)
                .values(**values)
                .on_conflict_do_nothing(**keys)
            )
        result = await self.session.execute(stmt)
        await self.session.commit()  # visible to a concurrent request before the slow send starts
        return result.rowcount == 1

    async def _finish(self, record_id: uuid.UUID, **values: object) -> None:
        await self.session.execute(
            update(Notification).where(Notification.id == record_id).values(**values)
        )
        await self.session.commit()

    async def _is_paid(self, order_id: uuid.UUID) -> bool:
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
        return (await self.session.execute(stmt)).first() is not None

    async def _notify(
        self, order_id: uuid.UUID, event: str, actor_user_id: uuid.UUID | None
    ) -> bool:
        cfg = self.cfg
        if not cfg.WHATSAPP_ENABLED or event not in EVENTS:
            return False
        template = getattr(cfg, _TEMPLATE_SETTING[event]).strip()
        if not template:
            return False

        order = await self.session.get(Order, order_id)
        if order is None:
            return False
        profile = await self.session.get(CustomerProfile, order.customer_profile_id)
        if profile is None or not profile.whatsapp_opt_in or not profile.whatsapp_phone:
            logger.info(
                "WhatsApp: skipped order=%s event=%s (no opt-in)", order_id, event
            )
            return False
        if event == ORDER_CANCELLED and actor_user_id == profile.user_id:
            return False  # the customer cancelled it themselves: they already know
        if not await self._is_paid(order_id):
            logger.info(
                "WhatsApp: skipped order=%s event=%s (not paid)", order_id, event
            )
            return False

        recipient = profile.whatsapp_phone
        allowed = _allowlist(cfg)
        if allowed and recipient not in allowed:
            logger.info(
                "WhatsApp: skipped %s (not on the test allow-list)",
                mask_phone(recipient),
            )
            return False

        provider = self._provider or build_whatsapp_provider(cfg)
        if provider is None:
            return False

        branch = await self.session.get(Branch, order.branch_id)
        # Read everything needed now: the session is committed (and may be rolled back) below.
        params = build_params(
            event,
            customer_name=profile.full_name,
            code=order_code(order.id),
            branch_name=branch.name if branch else "the stall",
            pickup_at=(order.delivery_address_snapshot or {}).get("pickup_at"),
            total=order.total_amount,
            now=datetime.now(UTC),
        )
        user_id = profile.user_id

        record_id = uuid7()
        claimed = await self._claim(
            {
                "id": record_id,
                "user_id": user_id,
                "channel": CHANNEL,
                "recipient": recipient,
                "subject": event,
                "body": render_preview(event, params),
                "status": "PENDING",
                "order_id": order_id,
                "event": event,
            }
        )
        if not claimed:
            # Already sent (or being sent) for this order and event: exactly what we want.
            logger.info("WhatsApp: already sent order=%s event=%s", order_id, event)
            return False

        try:
            message_id = await asyncio.wait_for(
                provider.send_template(
                    TemplateMessage(
                        to=recipient,
                        template=template,
                        language=cfg.WHATSAPP_LANGUAGE,
                        body_params=params,
                    )
                ),
                timeout=cfg.WHATSAPP_TIMEOUT_SECONDS + 0.5,
            )
        except TimeoutError:
            await self._finish(record_id, status="FAILED", error="WhatsApp timed out")
            logger.warning("WhatsApp: timed out order=%s event=%s", order_id, event)
            return False
        except WhatsAppSendError as exc:
            await self._finish(record_id, status="FAILED", error=str(exc)[:500])
            logger.warning(
                "WhatsApp: send failed order=%s event=%s to=%s: %s",
                order_id,
                event,
                mask_phone(recipient),
                exc,
            )
            return False
        except Exception as exc:
            await self._finish(
                record_id, status="FAILED", error=f"{type(exc).__name__}: {exc}"[:500]
            )
            logger.exception("WhatsApp: unexpected send failure order=%s", order_id)
            return False

        await self._finish(record_id, status="SENT", vendor_message_id=message_id)
        logger.info(
            "WhatsApp: sent order=%s event=%s to=%s",
            order_id,
            event,
            mask_phone(recipient),
        )
        return True


def get_whatsapp_notifier(
    session: AsyncSession = Depends(get_db_session),
) -> WhatsAppNotifier:
    return WhatsAppNotifier(session)
