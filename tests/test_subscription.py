import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.security import hash_password
from app.merchant.models import Merchant


@pytest.fixture
async def setup_sub_fixture(db_session: AsyncSession):
    user = User(
        email="merchant_sub_owner@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="MerchantOwner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=user.id,
        business_name="Sub Merchant",
        legal_entity_name="Sub Merchant Ltd",
        fssai_license_number="12345678901234",
    )
    db_session.add(merchant)
    await db_session.commit()

    return {"user": user, "merchant": merchant}


async def get_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_subscription_lifecycle(client: AsyncClient, setup_sub_fixture: dict):
    fixture = setup_sub_fixture
    headers = await get_headers(client, fixture["user"].email)

    # Get subscription (Auto-initializes to BASIC)
    sub_resp = await client.get("/api/v1/merchants/me/subscription", headers=headers)
    assert sub_resp.status_code == 200
    data = sub_resp.json()
    assert data["plan_tier"] == "BASIC"
    assert data["commission_rate_percentage"] == 5.0
    assert data["max_branches"] == 1

    # Upgrade to PROFESSIONAL
    up_resp = await client.post(
        "/api/v1/merchants/me/subscription",
        headers=headers,
        json={"plan_tier": "PROFESSIONAL", "billing_cycle": "MONTHLY"},
    )
    assert up_resp.status_code == 201
    up_data = up_resp.json()
    assert up_data["plan_tier"] == "PROFESSIONAL"
    assert up_data["commission_rate_percentage"] == 5.0
    assert up_data["max_branches"] == 5

    # Renew subscription
    renew_resp = await client.post(
        "/api/v1/merchants/me/subscription/renew",
        headers=headers,
        json={"duration_months": 3},
    )
    assert renew_resp.status_code == 200
    assert renew_resp.json()["plan_tier"] == "PROFESSIONAL"

    # Get invoices
    inv_resp = await client.get("/api/v1/merchants/me/invoices", headers=headers)
    assert inv_resp.status_code == 200
    invoices = inv_resp.json()
    assert len(invoices) >= 1
    assert invoices[0]["amount"] == 2499.0

    # Get QR Codes and payment links
    qr_resp = await client.get("/api/v1/merchants/me/qr-codes", headers=headers)
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert qr_data["merchant_id"] == str(fixture["merchant"].id)
    assert qr_data["plan_tier"] == "PROFESSIONAL"
    assert qr_data["plan_price"] == 2499
    assert qr_data["registration_fee_payment_link"] is not None
    assert qr_data["registration_fee_qr_url"] is not None
    assert qr_data["registration_expires_at"] is not None
    assert qr_data["plan_payment_link"] is not None
    assert qr_data["plan_qr_url"] is not None

    # Initiate fresh registration fee QR with countdown
    init_resp = await client.post("/api/v1/merchants/me/initiate-registration-fee", headers=headers)
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    assert init_data["registration_expires_at"] is not None

    # Switch plan to ENTERPRISE -> plan_price changes to 4999
    ent_resp = await client.post(
        "/api/v1/merchants/me/subscription",
        headers=headers,
        json={"plan_tier": "ENTERPRISE", "billing_cycle": "MONTHLY"},
    )
    assert ent_resp.status_code == 201

    qr_ent_resp = await client.get("/api/v1/merchants/me/qr-codes", headers=headers)
    assert qr_ent_resp.status_code == 200
    qr_ent_data = qr_ent_resp.json()
    assert qr_ent_data["plan_tier"] == "ENTERPRISE"
    assert qr_ent_data["plan_price"] == 4999
