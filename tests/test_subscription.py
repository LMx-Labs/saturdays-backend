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

    # No subscription or invoice is fabricated before a real payment path exists.
    sub_resp = await client.get("/api/v1/merchants/me/subscription", headers=headers)
    assert sub_resp.status_code == 404

    # Upgrade to PROFESSIONAL
    up_resp = await client.post(
        "/api/v1/merchants/me/subscription",
        headers=headers,
        json={"plan_tier": "PROFESSIONAL", "billing_cycle": "MONTHLY"},
    )
    assert up_resp.status_code == 503
    assert up_resp.json()["error_code"] == "PAYMENT_COLLECTION_UNAVAILABLE"

    # Renew subscription
    renew_resp = await client.post(
        "/api/v1/merchants/me/subscription/renew",
        headers=headers,
        json={"duration_months": 3},
    )
    assert renew_resp.status_code == 503

    # Get invoices
    inv_resp = await client.get("/api/v1/merchants/me/invoices", headers=headers)
    assert inv_resp.status_code == 200
    invoices = inv_resp.json()
    assert invoices == []
