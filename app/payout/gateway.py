import hashlib
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class PayoutGatewayError(Exception):
    """Razorpay call failed. ``retryable`` means the outcome is unknown or transient."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class GatewayPayout:
    id: str
    status: str  # raw Razorpay status
    utr: str | None = None
    failure_reason: str | None = None


class RazorpayXClient:
    """Minimal RazorpayX client: contacts, bank fund accounts, payouts.

    With ``RAZORPAY_SIMULATE`` (default outside production) nothing leaves the
    process and every payout "succeeds" with deterministic fake IDs.
    """

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        account_number: str | None = None,
        base_url: str | None = None,
        simulate: bool | None = None,
        timeout: float = 20.0,
    ):
        self.key_id = key_id if key_id is not None else settings.RAZORPAY_KEY_ID
        self.key_secret = (
            key_secret if key_secret is not None else settings.RAZORPAY_KEY_SECRET
        )
        self.account_number = (
            account_number
            if account_number is not None
            else settings.RAZORPAYX_ACCOUNT_NUMBER
        )
        self.base_url = (base_url or settings.RAZORPAY_BASE_URL).rstrip("/")
        self.simulate = settings.RAZORPAY_SIMULATE if simulate is None else simulate
        self.timeout = timeout

    # ----- HTTP --------------------------------------------------------

    async def _post(
        self, path: str, body: dict[str, Any], idempotency_key: str | None = None
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if idempotency_key:
            headers["X-Payout-Idempotency"] = idempotency_key
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    json=body,
                    headers=headers,
                    auth=(self.key_id, self.key_secret),
                )
        except httpx.HTTPError as exc:
            # Timeout / connection reset: we cannot know if Razorpay got it. The
            # idempotency key makes re-sending the same request safe.
            raise PayoutGatewayError(f"Razorpay unreachable: {exc!s}", True) from exc

        if resp.status_code >= 500 or resp.status_code == 429:
            raise PayoutGatewayError(
                f"Razorpay temporary error {resp.status_code}", retryable=True
            )
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
                detail = err.get("description") or resp.text
            except ValueError:
                detail = resp.text
            raise PayoutGatewayError(
                f"Razorpay rejected request ({resp.status_code}): {detail}"
            )
        return resp.json()

    # ----- operations --------------------------------------------------

    async def create_contact(
        self, name: str, reference_id: str, email: str | None = None
    ) -> str:
        if self.simulate:
            return f"cont_sim_{hashlib.sha1(reference_id.encode()).hexdigest()[:14]}"
        body: dict[str, Any] = {
            "name": name[:50],
            "type": "vendor",
            "reference_id": reference_id,
        }
        if email:
            body["email"] = email
        return (await self._post("/contacts", body))["id"]

    async def create_bank_fund_account(
        self, contact_id: str, name: str, ifsc: str, account_number: str
    ) -> str:
        if self.simulate:
            seed = f"{contact_id}|{ifsc}|{account_number}"
            return f"fa_sim_{hashlib.sha1(seed.encode()).hexdigest()[:14]}"
        body = {
            "contact_id": contact_id,
            "account_type": "bank_account",
            "bank_account": {
                "name": name[:120],
                "ifsc": ifsc,
                "account_number": account_number,
            },
        }
        return (await self._post("/fund_accounts", body))["id"]

    async def create_payout(
        self,
        fund_account_id: str,
        amount_paise: int,
        reference_id: str,
        narration: str,
        idempotency_key: str,
        currency: str = "INR",
    ) -> GatewayPayout:
        if self.simulate:
            return GatewayPayout(
                id=f"pout_sim_{hashlib.sha1(idempotency_key.encode()).hexdigest()[:14]}",
                status="processed",
                utr=f"SIM{hashlib.sha1(idempotency_key.encode()).hexdigest()[:12].upper()}",
            )
        body = {
            "account_number": self.account_number,
            "fund_account_id": fund_account_id,
            "amount": amount_paise,
            "currency": currency,
            # IMPS is instant but capped at 5 lakh; NEFT above that.
            "mode": "IMPS" if amount_paise <= 50_000_000 else "NEFT",
            "purpose": "payout",
            # If the RazorpayX balance is short, queue instead of failing; it is
            # released automatically once the account is topped up.
            "queue_if_low_balance": True,
            "reference_id": reference_id[:40],
            "narration": narration[:30],
        }
        data = await self._post("/payouts", body, idempotency_key=idempotency_key)
        return GatewayPayout(
            id=data["id"],
            status=data.get("status", "processing"),
            utr=data.get("utr"),
            failure_reason=(data.get("status_details") or {}).get("description"),
        )
