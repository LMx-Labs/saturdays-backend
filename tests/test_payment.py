import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.razorpay_adapter import RazorpayAdapter


@pytest.fixture
async def setup_payment_fixture(db_session: AsyncSession):
    """Helper fixture for Payment tests."""
    cust_user = User(
        email="pay_cust@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    manager_user = User(
        email="pay_mgr@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="BranchManager",
        is_active=True,
    )
    db_session.add_all([cust_user, manager_user])
    await db_session.flush()

    cust_profile = CustomerProfile(
        user_id=cust_user.id,
        full_name="Payment Customer",
        phone_number="9988776655",
    )
    db_session.add(cust_profile)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=manager_user.id,
        business_name="Pay Merchant",
        legal_entity_name="Pay Merchant LLC",
        fssai_license_number="11223344556677",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Pay Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(brand_id=brand.id, name="Pay Branch", address_text="Main Street")
    db_session.add(branch)
    await db_session.flush()

    order = Order(
        customer_profile_id=cust_profile.id,
        branch_id=branch.id,
        total_amount=500.00,
        status="PLACED",
        delivery_address_snapshot={"address_line": "Hostel 1"},
    )
    db_session.add(order)
    await db_session.commit()

    cust_token = create_access_token(subject=str(cust_user.id), role=cust_user.role)
    mgr_token = create_access_token(
        subject=str(manager_user.id), role=manager_user.role
    )

    return {
        "cust_user": cust_user,
        "cust_profile": cust_profile,
        "manager_user": manager_user,
        "branch": branch,
        "order": order,
        "cust_headers": {"Authorization": f"Bearer {cust_token}"},
        "mgr_headers": {"Authorization": f"Bearer {mgr_token}"},
    }


@pytest.mark.asyncio
async def test_payment_intent_creation(
    client: AsyncClient, setup_payment_fixture: dict
):
    ctx = setup_payment_fixture
    order_id = ctx["order"].id
    headers = ctx["cust_headers"]

    payload = {
        "order_id": str(order_id),
        "amount": 500.00,
        "currency": "INR",
    }
    response = await client.post(
        "/api/v1/payments/intent", json=payload, headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["order_id"] == str(order_id)
    assert data["amount"] == 500.00
    assert data["razorpay_order_id"].startswith("order_sim_")
    assert data["key_id"] == settings.RAZORPAY_KEY_ID
    assert data["is_simulated"] is True
    assert "key_secret" not in response.text
    if settings.RAZORPAY_KEY_SECRET:
        assert settings.RAZORPAY_KEY_SECRET not in response.text


@pytest.mark.asyncio
async def test_successful_and_failed_payment_verification(
    client: AsyncClient, setup_payment_fixture: dict
):
    ctx = setup_payment_fixture
    order_id = ctx["order"].id
    headers = ctx["cust_headers"]

    # 1. Create Intent
    intent_res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(order_id), "amount": 500.00},
        headers=headers,
    )
    rzp_order_id = str(intent_res.json()["razorpay_order_id"])
    rzp_pay_id = f"pay_{uuid.uuid4().hex[:10]}"

    # 2. Failed Verification (Invalid Signature)
    invalid_verify_payload = {
        "order_id": str(order_id),
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": rzp_pay_id,
        "razorpay_signature": "invalid_signature_hex",
    }
    bad_res = await client.post(
        "/api/v1/payments/verify", json=invalid_verify_payload, headers=headers
    )
    assert bad_res.status_code == 400
    assert bad_res.json()["error_code"] == "INVALID_PAYMENT_SIGNATURE"

    # 3. Successful Verification
    adapter = RazorpayAdapter()
    msg = f"{rzp_order_id}|{rzp_pay_id}".encode()
    valid_sig = hmac.new(
        (adapter.key_secret or "").encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()

    valid_verify_payload = {
        "order_id": str(order_id),
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": rzp_pay_id,
        "razorpay_signature": valid_sig,
    }
    good_res = await client.post(
        "/api/v1/payments/verify", json=valid_verify_payload, headers=headers
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "CAPTURED"


@pytest.mark.asyncio
async def test_webhook_verification_and_duplicate_idempotency(
    client: AsyncClient, setup_payment_fixture: dict
):
    ctx = setup_payment_fixture
    order_id = ctx["order"].id
    headers = ctx["cust_headers"]

    intent_res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(order_id), "amount": 500.00},
        headers=headers,
    )
    rzp_order_id = str(intent_res.json()["razorpay_order_id"])
    rzp_pay_id = f"pay_wh_{uuid.uuid4().hex[:10]}"

    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": rzp_pay_id,
                    "order_id": rzp_order_id,
                    "amount": 50000,
                }
            }
        },
    }
    raw_body = json.dumps(webhook_payload)
    adapter = RazorpayAdapter()
    sig = hmac.new(
        (adapter.webhook_secret or "").encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # First webhook request
    wh_res = await client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "processed"

    # Duplicate webhook request (Idempotency check)
    dup_res = await client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["status"] == "ignored"
    assert dup_res.json()["reason"] == "DUPLICATE_WEBHOOK"


@pytest.mark.asyncio
async def test_refund_flow_and_cap_invariant(
    client: AsyncClient, setup_payment_fixture: dict, monkeypatch
):
    monkeypatch.setattr(settings, "REFUNDS_ENABLED", True)
    ctx = setup_payment_fixture
    order_id = ctx["order"].id
    headers = ctx["cust_headers"]
    mgr_headers = ctx["mgr_headers"]

    intent_res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(order_id), "amount": 500.00},
        headers=headers,
    )
    payment_id = intent_res.json()["payment_id"]

    # 1. Refund partial amount (200.00 out of 500.00)
    rf_res = await client.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amount": 200.00, "reason": "PARTIAL_CANCEL"},
        headers=mgr_headers,
    )
    assert rf_res.status_code == 201
    assert rf_res.json()["amount"] == 200.00

    # 2. Refund remaining amount (300.00 out of 500.00)
    rf_res2 = await client.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amount": 300.00, "reason": "FULL_CANCEL"},
        headers=mgr_headers,
    )
    assert rf_res2.status_code == 201

    # 3. Exceed refund cap invariant check (attempting additional 100.00 refund)
    bad_rf = await client.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amount": 100.00, "reason": "OVER_REFUND"},
        headers=mgr_headers,
    )
    assert bad_rf.status_code == 400
    assert bad_rf.json()["error_code"] == "REFUND_EXCEEDS_PAYMENT_AMOUNT"


@pytest.mark.asyncio
async def test_cash_refund_is_disabled_by_policy(
    client: AsyncClient, setup_payment_fixture: dict
):
    ctx = setup_payment_fixture
    intent_res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(ctx["order"].id), "amount": 500.00},
        headers=ctx["cust_headers"],
    )
    payment_id = intent_res.json()["payment_id"]

    rf_res = await client.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amount": 100.00, "reason": "CANCELLED"},
        headers=ctx["mgr_headers"],
    )
    assert rf_res.status_code == 400
    assert rf_res.json()["error_code"] == "REFUNDS_DISABLED_USE_STORE_CREDIT"


@pytest.fixture(autouse=True)
def _simulate_razorpay_orders(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", True)


@pytest.mark.asyncio
async def test_live_razorpay_order_uses_paise_and_basic_auth(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_public")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp_test_secret")
    monkeypatch.setattr(settings, "RAZORPAY_BASE_URL", "https://api.razorpay.com/v1/")
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "id": "order_live_abc",
                "amount": 49900,
                "currency": "INR",
                "status": "created",
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["init"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, auth):
            captured["url"] = url
            captured["json"] = json
            captured["auth"] = auth
            return FakeResponse()

    monkeypatch.setattr(
        "app.payment.razorpay_adapter.httpx.AsyncClient", FakeClient
    )
    result = await RazorpayAdapter().create_order(499, "INR", receipt="booking-1")
    assert result["id"] == "order_live_abc"
    assert captured["url"] == "https://api.razorpay.com/v1/orders"
    assert captured["json"] == {
        "amount": 49900,
        "currency": "INR",
        "receipt": "booking-1",
    }
    assert type(captured["json"]["amount"]) is int
    assert captured["auth"] == ("rzp_test_public", "rzp_test_secret")
    assert "rzp_test_secret" not in json.dumps(result)
