import hashlib
import hmac
import uuid
from typing import Any

from app.core.config import get_settings

settings = get_settings()


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

    def create_order(
        self, amount: float, currency: str = "INR", receipt: str | None = None
    ) -> dict[str, Any]:
        """Creates Razorpay Order ID."""
        amount_in_paise = int(amount * 100)
        razorpay_order_id = f"order_rzp_{uuid.uuid4().hex[:12]}"
        return {
            "id": razorpay_order_id,
            "entity": "order",
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": receipt or str(uuid.uuid4()),
            "status": "created",
        }

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
