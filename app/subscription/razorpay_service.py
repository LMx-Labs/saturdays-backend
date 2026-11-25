"""Razorpay API wrapper for subscription and payment operations.

Uses httpx with Basic Auth (key_id:key_secret) to call Razorpay REST API.
All amounts are in INR paise (₹1 = 100 paise).
"""
import hashlib
import hmac
import time
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

RAZORPAY_BASE = "https://api.razorpay.com/v1"


def _auth() -> tuple[str, str]:
    return (settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or "")


def _simulate() -> bool:
    return settings.RAZORPAY_SIMULATE


async def create_razorpay_plan(tier: str, price_monthly: int, name: str) -> dict[str, Any]:
    """POST /v1/plans — creates a Razorpay subscription plan.
    Returns the full Razorpay plan object; caller should store plan["id"].
    """
    if _simulate():
        logger.info("SIMULATE: create_razorpay_plan", tier=tier, price=price_monthly)
        return {"id": f"plan_SIMULATED_{tier}", "interval": 1, "period": "monthly"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{RAZORPAY_BASE}/plans",
            auth=_auth(),
            json={
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": f"Saturdays Platform — {name}",
                    "amount": price_monthly * 100,
                    "currency": "INR",
                    "description": f"Saturdays monthly subscription: {name}",
                },
            },
        )
        resp.raise_for_status()
        return resp.json()


async def create_razorpay_subscription(
    razorpay_plan_id: str,
    total_count: int = 120,
    notify_whatsapp: bool = False,
) -> dict[str, Any]:
    """POST /v1/subscriptions — creates a recurring subscription for a merchant."""
    if _simulate():
        logger.info("SIMULATE: create_razorpay_subscription", plan_id=razorpay_plan_id)
        return {"id": f"sub_SIMULATED_{razorpay_plan_id[:8]}", "status": "created"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{RAZORPAY_BASE}/subscriptions",
            auth=_auth(),
            json={
                "plan_id": razorpay_plan_id,
                "total_count": total_count,
                "quantity": 1,
                "notify_info": {"notify_whatsapp": int(notify_whatsapp)},
            },
        )
        resp.raise_for_status()
        return resp.json()


async def cancel_razorpay_subscription(
    razorpay_sub_id: str,
    cancel_at_cycle_end: bool = True,
) -> dict[str, Any]:
    """POST /v1/subscriptions/{id}/cancel"""
    if _simulate():
        logger.info("SIMULATE: cancel_razorpay_subscription", sub_id=razorpay_sub_id)
        return {"id": razorpay_sub_id, "status": "cancelled"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{RAZORPAY_BASE}/subscriptions/{razorpay_sub_id}/cancel",
            auth=_auth(),
            json={"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_razorpay_subscription(razorpay_sub_id: str) -> dict[str, Any]:
    """GET /v1/subscriptions/{id}"""
    if _simulate():
        return {"id": razorpay_sub_id, "status": "active"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{RAZORPAY_BASE}/subscriptions/{razorpay_sub_id}",
            auth=_auth(),
        )
        resp.raise_for_status()
        return resp.json()


async def create_registration_payment_link(
    merchant_id: str,
    merchant_name: str,
) -> dict[str, Any]:
    """POST /v1/payment_links — ₹500 one-time registration fee link with QR."""
    if _simulate():
        logger.info("SIMULATE: create_registration_payment_link", merchant_id=merchant_id)
        return {
            "id": f"plink_SIMULATED_{merchant_id[:8]}",
            "short_url": f"https://rzp.io/l/SIMULATED_{merchant_id[:6]}",
        }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{RAZORPAY_BASE}/payment_links",
            auth=_auth(),
            json={
                "amount": 50000,  # ₹500 in paise
                "currency": "INR",
                "description": f"Saturdays Platform Registration Fee — {merchant_name}",
                "reference_id": f"REG-{merchant_id[:8].upper()}",
                "notes": {
                    "merchant_id": merchant_id,
                    "type": "REGISTRATION_FEE",
                },
                "options": {
                    "checkout": {
                        "name": "Saturdays Platform",
                        "description": "One-time restaurant registration fee",
                    }
                },
            },
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_settlements(
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> dict[str, Any]:
    """GET /v1/settlements"""
    if _simulate():
        return {"items": [], "count": 0}

    params: dict[str, Any] = {}
    if from_ts:
        params["from"] = from_ts
    if to_ts:
        params["to"] = to_ts

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{RAZORPAY_BASE}/settlements",
            auth=_auth(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
