"""The upstream live-order adapter remains covered while collection stays gated."""

import json

import pytest

from app.payment.razorpay_adapter import RazorpayAdapter, settings


@pytest.mark.asyncio
async def test_provider_order_uses_integer_paise_and_basic_auth(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_public")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp_test_secret")
    monkeypatch.setattr(settings, "RAZORPAY_BASE_URL", "https://api.razorpay.com/v1/")
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"id": "order_live_abc", "amount": 49900, "currency": "INR"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, auth):
            captured.update(url=url, json=json, auth=auth)
            return FakeResponse()

    monkeypatch.setattr("app.payment.razorpay_adapter.httpx.AsyncClient", FakeClient)
    result = await RazorpayAdapter().create_order(499, "INR", receipt="booking-1")
    assert result["id"] == "order_live_abc"
    assert captured == {
        "url": "https://api.razorpay.com/v1/orders",
        "json": {"amount": 49900, "currency": "INR", "receipt": "booking-1"},
        "auth": ("rzp_test_public", "rzp_test_secret"),
    }
    assert "rzp_test_secret" not in json.dumps(result)
