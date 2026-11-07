"""What WhatsApp tells us back: delivery reports, and customers replying "STOP"."""

import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.customer.models import CustomerProfile
from app.notification.models import Notification
from app.notification.whatsapp_service import CHANNEL

logger = logging.getLogger(__name__)

# What a customer can reply to stop all WhatsApp messages. ("cancel" is left out on purpose:
# someone saying "cancel" probably means their order, not the updates.)
STOP_WORDS = {"stop", "stop all", "unsubscribe", "opt out", "optout", "stop messages"}

_STATUS_NAMES = {
    "sent": "SENT",
    "delivered": "DELIVERED",
    "read": "READ",
    "failed": "FAILED",
}
_RANK = {"PENDING": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}


def signature_is_valid(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """WhatsApp signs every webhook call with the app secret ("sha256=<hex of the body>")."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def _when(timestamp: object) -> datetime:
    try:
        return datetime.fromtimestamp(int(str(timestamp)), tz=UTC)
    except (ValueError, TypeError, OSError):
        return datetime.now(UTC)


async def _apply_status(session: AsyncSession, report: dict) -> bool:
    message_id = report.get("id")
    new = _STATUS_NAMES.get(str(report.get("status", "")).lower())
    if not message_id or new is None:
        return False
    stmt = select(Notification).where(
        Notification.vendor_message_id == message_id, Notification.channel == CHANNEL
    )
    record = (await session.execute(stmt)).scalars().first()
    if record is None:
        return False

    if new == "FAILED":
        if record.status in ("DELIVERED", "READ"):
            return False  # a late failure report must not undo a delivery
        errors = report.get("errors") or [{}]
        first = errors[0] if isinstance(errors[0], dict) else {}
        detail = first.get("title") or first.get("message") or "failed"
        record.status = "FAILED"
        record.error = f"{first.get('code', '')}: {detail}".strip(": ")[:500]
        return True

    # Reports can arrive out of order: never move a message backwards ("read" then "delivered").
    if _RANK[new] <= _RANK.get(record.status, -1):
        return False
    record.status = new
    when = _when(report.get("timestamp"))
    if new in ("DELIVERED", "READ") and record.delivered_at is None:
        record.delivered_at = when
    if new == "READ":
        record.read_at = when
    return True


async def _apply_inbound(session: AsyncSession, message: dict) -> int:
    """A customer wrote to us. If it's "STOP", switch their WhatsApp updates off. Returns how many
    customers were switched off."""
    if message.get("type") != "text":
        return 0
    text = re.sub(
        r"[^a-z ]", "", str((message.get("text") or {}).get("body", "")).lower()
    ).strip()
    if text not in STOP_WORDS:
        return 0
    sender = re.sub(r"\D", "", str(message.get("from", "")))
    if not sender:
        return 0
    stmt = select(CustomerProfile).where(CustomerProfile.whatsapp_phone == sender)
    switched = 0
    for profile in (await session.execute(stmt)).scalars().all():
        profile.whatsapp_opt_in = False
        profile.whatsapp_phone = None
        switched += 1
    if switched:
        logger.info("WhatsApp: %d customer(s) opted out by replying STOP", switched)
    return switched


async def process_webhook(session: AsyncSession, payload: dict) -> dict[str, int]:
    updated = opted_out = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for report in value.get("statuses") or []:
                if await _apply_status(session, report):
                    updated += 1
            for message in value.get("messages") or []:
                opted_out += await _apply_inbound(session, message)
    await session.commit()
    return {"updated": updated, "opted_out": opted_out}
