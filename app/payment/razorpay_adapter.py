import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from base64 import b64encode
from typing import Any
from urllib.request import Request, urlopen

from app.core.config import get_settings

settings = get_settings()


class PaymentGateway(ABC):
    provider: str

    @abstractmethod
    def create_order(
        self, amount: float, currency: str = "INR", receipt: str | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    def verify_payment_signature(
        self, provider_order_id: str, provider_payment_id: str, signature: str
    ) -> bool: ...

    @abstractmethod
    def verify_webhook_signature(self, body: str | bytes, signature: str) -> bool: ...

    @abstractmethod
    def create_refund(self, provider_payment_id: str, amount: float) -> dict[str, Any]: ...


class MockPaymentGateway(PaymentGateway):
    provider = "mock"

    def __init__(self, key_secret: str | None = None, webhook_secret: str | None = None):
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET or "dummy_secret"
        self.webhook_secret = (
            webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET or "dummy_webhook_secret"
        )

    def create_order(
        self, amount: float, currency: str = "INR", receipt: str | None = None
    ) -> dict[str, Any]:
        """Creates Razorpay Order ID."""
        amount_in_paise = int(amount * 100)
        seed = f"{receipt}|{amount_in_paise}|{currency}"
        razorpay_order_id = f"order_mock_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        return {
            "id": razorpay_order_id,
            "entity": "order",
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": receipt or "local",
            "status": "created",
        }

    def verify_payment_signature(
        self,
        provider_order_id: str | None = None,
        provider_payment_id: str | None = None,
        signature: str | None = None,
        secret: str | None = None,
        **legacy: Any,
    ) -> bool:
        provider_order_id = provider_order_id or legacy.get("razorpay_order_id", "")
        provider_payment_id = provider_payment_id or legacy.get("razorpay_payment_id", "")
        signature = signature or legacy.get("razorpay_signature", "")
        key_secret = secret or self.key_secret or ""
        msg = f"{provider_order_id}|{provider_payment_id}".encode()
        generated_signature = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_signature, signature)

    def verify_webhook_signature(
        self,
        body: str | bytes,
        signature: str,
        secret: str | None = None,
    ) -> bool:
        """Verifies Razorpay Webhook HMAC SHA256 signature."""
        webhook_secret = secret or self.webhook_secret or ""
        payload_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
        generated_signature = hmac.new(
            webhook_secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated_signature, signature)

    def create_refund(self, provider_payment_id: str, amount: float) -> dict[str, Any]:
        """Issues refund via Razorpay."""
        amount_in_paise = int(amount * 100)
        seed = f"{provider_payment_id}|{amount_in_paise}"
        refund_id = f"rfnd_mock_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        return {
            "id": refund_id,
            "entity": "refund",
            "amount": amount_in_paise,
            "payment_id": provider_payment_id,
            "status": "processed",
        }


class RazorpayGateway(MockPaymentGateway):
    provider = "razorpay"

    def __init__(self) -> None:
        super().__init__(settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET)
        self.key_id = settings.RAZORPAY_KEY_ID or ""

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        credentials = b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = Request(
            f"https://api.razorpay.com/v1/{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read())

    def create_order(
        self, amount: float, currency: str = "INR", receipt: str | None = None
    ) -> dict[str, Any]:
        return self._request(
            "orders",
            {
                "amount": int(round(amount * 100)),
                "currency": currency,
                "receipt": receipt,
            },
        )

    def create_refund(self, provider_payment_id: str, amount: float) -> dict[str, Any]:
        return self._request(
            f"payments/{provider_payment_id}/refund",
            {"amount": int(round(amount * 100))},
        )


class RazorpayAdapter(MockPaymentGateway):
    """Backward-compatible deterministic local adapter."""


def get_payment_gateway() -> PaymentGateway:
    if settings.PAYMENT_PROVIDER.lower() == "razorpay":
        return RazorpayGateway()
    return MockPaymentGateway()
