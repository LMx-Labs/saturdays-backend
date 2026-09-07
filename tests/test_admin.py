import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import hash_password
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction


@pytest.fixture
async def setup_admin_fixture(db_session: AsyncSession):
    # Admin User
    admin_user = User(
        email="platform_admin@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="PlatformAdmin",
        is_active=True,
    )

    # Regular Merchant Owner User
    merchant_user = User(
        email="pending_merchant_owner@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="MerchantOwner",
        is_active=True,
    )
    customer_user = User(
        email="admin_refund_customer@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )

    db_session.add_all([admin_user, merchant_user, customer_user])
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=merchant_user.id,
        business_name="Pending Onboarding Store",
        legal_entity_name="Pending Store LLC",
        fssai_license_number="12345678901234",
        status="PENDING",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Refund Brand")
    profile = CustomerProfile(user_id=customer_user.id, full_name="Refund Customer")
    db_session.add_all([brand, profile])
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Refund Branch", address_text="Campus")
    db_session.add(branch)
    await db_session.flush()
    order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        total_amount=500,
        subtotal=500,
        status="CANCELLED",
        delivery_address_snapshot={"address_line": "Campus"},
    )
    db_session.add(order)
    await db_session.flush()
    payment = Payment(
        order_id=order.id,
        customer_profile_id=profile.id,
        amount=500,
        currency="INR",
        provider="mock",
        provider_order_id="order_admin_refund",
    )
    db_session.add(payment)
    await db_session.flush()
    db_session.add(
        PaymentTransaction(
            payment_id=payment.id,
            transaction_type="CAPTURED",
            razorpay_payment_id="pay_admin_refund",
            razorpay_order_id="order_admin_refund",
            amount=500,
            status="SUCCESS",
        )
    )
    await db_session.commit()

    return {"admin_user": admin_user, "merchant": merchant, "payment": payment}


async def get_admin_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_merchant_approval_and_audit(client: AsyncClient, setup_admin_fixture: dict):
    fixture = setup_admin_fixture
    headers = await get_admin_headers(client, fixture["admin_user"].email)

    merchant_id = str(fixture["merchant"].id)

    # Approve merchant
    app_resp = await client.post(
        f"/api/v1/admin/merchants/{merchant_id}/approval",
        headers=headers,
        json={"action": "APPROVE", "reason": "GSTIN and FSSAI verified."},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "APPROVED"

    # Check audit log
    audit_resp = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "MERCHANT_APPROVED"


@pytest.mark.asyncio
async def test_admin_banner_cms_and_feature_flags(client: AsyncClient, setup_admin_fixture: dict):
    fixture = setup_admin_fixture
    headers = await get_admin_headers(client, fixture["admin_user"].email)

    # 1. Create banner
    banner_payload = {
        "title": "Welcome Fest 2026",
        "image_url": "https://cdn.saturdays.com/banners/fest.png",
        "target_url": "https://saturdays.com/fest",
        "display_order": 1,
        "is_active": True,
    }
    banner_resp = await client.post("/api/v1/admin/banners", headers=headers, json=banner_payload)
    assert banner_resp.status_code == 201
    banner_id = banner_resp.json()["id"]

    # 2. List banners
    list_resp = await client.get("/api/v1/admin/banners")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 3. Delete banner
    del_resp = await client.delete(f"/api/v1/admin/banners/{banner_id}", headers=headers)
    assert del_resp.status_code == 204

    # 4. Feature flags
    flags_resp = await client.get("/api/v1/admin/feature-flags", headers=headers)
    assert flags_resp.status_code == 200
    assert len(flags_resp.json()) >= 2

    # Toggle EMERGENCY_MAINTENANCE_MODE
    toggle_resp = await client.put(
        "/api/v1/admin/feature-flags/EMERGENCY_MAINTENANCE_MODE",
        headers=headers,
        json={"enabled": True, "value": "Network outage"},
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_admin_refund_and_analytics(
    client: AsyncClient, db_session: AsyncSession, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    headers = await get_admin_headers(client, fixture["admin_user"].email)

    # Refund override
    ref_payload = {
        "payment_id": str(fixture["payment"].id),
        "amount": 250.0,
        "reason": "Customer complaint dispute resolution",
    }
    ref_resp = await client.post(
        "/api/v1/admin/refunds/override", headers=headers, json=ref_payload
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["status"] == "PROCESSED"
    refund = await db_session.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.id == uuid.UUID(ref_resp.json()["refund_transaction_id"])
        )
    )
    assert refund is not None
    assert refund.transaction_type == "REFUNDED"

    # Analytics overview
    analytics_resp = await client.get("/api/v1/admin/analytics/overview", headers=headers)
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert "total_merchants" in data
    assert "gross_revenue" in data
