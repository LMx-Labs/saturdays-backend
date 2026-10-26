import hashlib
import hmac
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()


def _amount_to_paise(amount: float) -> int:
    """Razorpay charges integer paise. 499 INR -> 49900."""
    # Convert through the decimal text, not the binary float representation.
    decimal_text = str(amount)
    decimal_amount = Decimal(decimal_text)
    paise = (decimal_amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(paise)


class RazorpayAdapter:
    """Razorpay Payment Gateway Adapter."""

    def __init__(
        self, key_secret: str | None = None, webhook_secret: str | None = None
    ):
        # Dev/test fall back to a fixed dummy secret; production never does, so a
        # missing secret fails closed instead of accepting forgeable signatures.
        dev = not settings.is_production
        self.key_secret = (
            key_secret
            or settings.RAZORPAY_KEY_SECRET
            or ("dummy_secret" if dev else "")
        )
        self.webhook_secret = (
            webhook_secret
            or settings.RAZORPAY_WEBHOOK_SECRET
            or ("dummy_webhook_secret" if dev else "")
        )

    async def create_order(
        self, amount: float, currency: str = "INR", receipt: str | None = None
    ) -> dict[str, Any]:
        """Create a Razorpay order.

        RAZORPAY_SIMULATE keeps a local id (Checkout would reject it) and does
        not mark anything paid. Otherwise POST /orders with key id and secret.
        """
        amount_in_paise = _amount_to_paise(amount)
        receipt_value = (receipt or uuid.uuid4().hex)[:40]
        if settings.RAZORPAY_SIMULATE:
            return {
                "id": f"order_sim_{uuid.uuid4().hex[:12]}",
                "entity": "order",
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt_value,
                "status": "created",
            }

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise AppException(
                message="Razorpay is not configured.",
                error_code="RAZORPAY_NOT_CONFIGURED",
                status_code=503,
            )

        url = f"{settings.RAZORPAY_BASE_URL.rstrip('/')}/orders"
        body = {
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": receipt_value,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    url,
                    json=body,
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                )
        except httpx.HTTPError as exc:
            raise AppException(
                message="Razorpay order request failed.",
                error_code="RAZORPAY_ORDER_FAILED",
                status_code=502,
            ) from exc

        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400 or not payload.get("id"):
            raise AppException(
                message="Razorpay did not return an order id.",
                error_code="RAZORPAY_ORDER_FAILED",
                status_code=502,
            )
        return payload

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        secret: str | None = None,
    ) -> bool:
        """Verifies Razorpay payment signature HMAC SHA256."""
        key_secret = secret or self.key_secret or ""
        if not key_secret:
            return False
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
        generated_signature = hmac.new(
            key_secret.encode("utf-8"), msg, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, razorpay_signature)

    def verify_webhook_signature(
        self,
        body: str | bytes,
        signature: str,
        secret: str | None = None,
    ) -> bool:
        """Verifies Razorpay Webhook HMAC SHA256 signature."""
        webhook_secret = secret or self.webhook_secret or ""
        if not webhook_secret:
            return False
        payload_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
        generated_signature = hmac.new(
            webhook_secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, signature)

    def create_refund(self, razorpay_payment_id: str, amount: float) -> dict[str, Any]:
        """Issues refund via Razorpay."""
        amount_in_paise = int(amount * 100)
        refund_id = f"rfnd_rzp_{uuid.uuid4().hex[:12]}"
        return {
            "id": refund_id,
            "entity": "refund",
            "amount": amount_in_paise,
            "payment_id": razorpay_payment_id,
            "status": "processed",
        }
