"""Payment collection must fail closed until the production mode is chosen."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.models import Payment


@pytest.fixture
async def payment_context(db_session: AsyncSession):
    customer = User(email="pay_customer@example.com", role="Customer", is_active=True)
    stranger = User(email="pay_stranger@example.com", role="Customer", is_active=True)
    owner = User(email="pay_owner@example.com", role="MerchantOwner", is_active=True)
    db_session.add_all([customer, stranger, owner])
    await db_session.flush()
    profile = CustomerProfile(user_id=customer.id, full_name="Pay Customer")
    stranger_profile = CustomerProfile(user_id=stranger.id, full_name="Other Customer")
    db_session.add_all([profile, stranger_profile])
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Pay Merchant",
        legal_entity_name="Pay Merchant",
        fssai_license_number="12345678901234",
        status="APPROVED",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Pay Brand")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Pay Branch", address_text="Pay Lane")
    db_session.add(branch)
    await db_session.flush()
    order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        total_amount=20,
        status="PLACED",
        delivery_address_snapshot={"address_line": "Test"},
    )
    db_session.add(order)
    await db_session.flush()
    payment = Payment(
        order_id=order.id, customer_profile_id=profile.id, amount=20, currency="INR"
    )
    db_session.add(payment)
    await db_session.commit()
    return {
        "order": order,
        "payment": payment,
        "customer": {
            "Authorization": f"Bearer {create_access_token(subject=str(customer.id), role='Customer')}"
        },
        "stranger": {
            "Authorization": f"Bearer {create_access_token(subject=str(stranger.id), role='Customer')}"
        },
        "owner": {
            "Authorization": f"Bearer {create_access_token(subject=str(owner.id), role='MerchantOwner')}"
        },
    }


@pytest.mark.asyncio
async def test_unsafe_payment_mutations_are_unavailable(
    client: AsyncClient, payment_context: dict, db_session: AsyncSession
):
    ctx = payment_context
    intent = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(ctx["order"].id), "amount": 0.01, "currency": "INR"},
        headers=ctx["customer"],
    )
    assert intent.status_code == 503
    assert intent.json()["error_code"] == "PAYMENT_COLLECTION_UNAVAILABLE"
    verify = await client.post(
        "/api/v1/payments/verify",
        json={
            "order_id": str(ctx["order"].id),
            "razorpay_order_id": "wrong-order",
            "razorpay_payment_id": "replayed-payment",
            "razorpay_signature": "signature",
        },
        headers=ctx["customer"],
    )
    assert verify.status_code == 503
    webhook = await client.post(
        "/api/v1/payments/webhook",
        content=b"{}",
        headers={"X-Razorpay-Signature": "signature"},
    )
    assert webhook.status_code == 503
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 1


@pytest.mark.asyncio
async def test_payment_history_is_resource_scoped(
    client: AsyncClient, payment_context: dict
):
    ctx = payment_context
    url = f"/api/v1/payments/{ctx['payment'].id}"
    assert (await client.get(url, headers=ctx["stranger"])).status_code == 403
    assert (await client.get(url, headers=ctx["customer"])).status_code == 200
    assert (await client.get(url, headers=ctx["owner"])).status_code == 200
    assert (await client.get(url)).status_code == 401
