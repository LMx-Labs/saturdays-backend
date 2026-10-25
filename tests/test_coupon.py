import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.security import hash_password
from app.coupon.models import Coupon, CouponRedemption
from app.customer.models import CustomerProfile


@pytest.fixture
async def setup_coupon_fixture(db_session: AsyncSession):
    # Customer user
    user = User(
        email="coupon_user@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    profile = CustomerProfile(user_id=user.id, full_name="Coupon Tester")
    db_session.add(profile)
    await db_session.flush()

    branch_id = uuid.uuid4()
    other_branch_id = uuid.uuid4()

    now = datetime.now(UTC)

    # 1. Platform Coupon: WELCOME50 (50% off up to ₹100, min order ₹200)
    platform_coupon = Coupon(
        code="WELCOME50",
        branch_id=None,  # Platform coupon
        discount_type="PERCENTAGE",
        discount_value=50.0,
        max_discount_amount=100.0,
        min_order_amount=200.0,
        max_redemptions_per_user=2,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=10),
        is_active=True,
    )

    # 2. Restaurant / Branch-Specific Coupon: STORE100 (Flat ₹100 off, min order ₹300)
    restaurant_coupon = Coupon(
        code="STORE100",
        branch_id=branch_id,
        discount_type="FLAT",
        discount_value=100.0,
        max_discount_amount=None,
        min_order_amount=300.0,
        max_redemptions_per_user=1,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=10),
        is_active=True,
    )

    # 3. Expired Coupon
    expired_coupon = Coupon(
        code="EXPIRED20",
        branch_id=None,
        discount_type="FLAT",
        discount_value=20.0,
        min_order_amount=50.0,
        valid_from=now - timedelta(days=10),
        valid_until=now - timedelta(days=1),
        is_active=True,
    )

    db_session.add_all([platform_coupon, restaurant_coupon, expired_coupon])
    await db_session.commit()

    return {
        "user": user,
        "profile": profile,
        "branch_id": branch_id,
        "other_branch_id": other_branch_id,
        "platform_coupon": platform_coupon,
        "restaurant_coupon": restaurant_coupon,
        "expired_coupon": expired_coupon,
    }


async def get_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_platform_coupon_validation_and_max_cap(
    client: AsyncClient, setup_coupon_fixture: dict
):
    fixture = setup_coupon_fixture
    headers = await get_headers(client, fixture["user"].email)

    # Validate platform coupon on order amount 500
    # 50% of 500 = 250, but capped at max_discount_amount = 100
    val_payload = {
        "code": "WELCOME50",
        "order_amount": 500.0,
    }
    resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=val_payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["discount_amount"] == 100.0
    assert data["final_amount"] == 400.0

    # Validate platform coupon on order amount 150 (below min_order_amount 200)
    low_payload = {"code": "WELCOME50", "order_amount": 150.0}
    low_resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=low_payload
    )
    assert low_resp.status_code == 422
    assert low_resp.json()["error_code"] == "MINIMUM_ORDER_AMOUNT_NOT_MET"


@pytest.mark.asyncio
async def test_restaurant_coupon_branch_scope_validation(
    client: AsyncClient, setup_coupon_fixture: dict
):
    fixture = setup_coupon_fixture
    headers = await get_headers(client, fixture["user"].email)

    # Validate with matching branch_id
    valid_payload = {
        "code": "STORE100",
        "order_amount": 400.0,
        "branch_id": str(fixture["branch_id"]),
    }
    resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=valid_payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["discount_amount"] == 100.0
    assert data["final_amount"] == 300.0

    # Validate with wrong branch_id (branch mismatch)
    wrong_branch_payload = {
        "code": "STORE100",
        "order_amount": 400.0,
        "branch_id": str(fixture["other_branch_id"]),
    }
    mismatch_resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=wrong_branch_payload
    )
    assert mismatch_resp.status_code == 422
    assert mismatch_resp.json()["error_code"] == "COUPON_BRANCH_MISMATCH"


@pytest.mark.asyncio
async def test_expired_coupon_validation(
    client: AsyncClient, setup_coupon_fixture: dict
):
    fixture = setup_coupon_fixture
    headers = await get_headers(client, fixture["user"].email)

    exp_payload = {"code": "EXPIRED20", "order_amount": 100.0}
    resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=exp_payload
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "COUPON_EXPIRED"


@pytest.mark.asyncio
async def test_coupon_user_redemption_limit(
    client: AsyncClient, setup_coupon_fixture: dict, db_session: AsyncSession
):
    fixture = setup_coupon_fixture
    headers = await get_headers(client, fixture["user"].email)

    coupon = fixture["restaurant_coupon"]  # max 1 redemption
    profile = fixture["profile"]

    # Record 1 redemption manually
    redemption = CouponRedemption(
        coupon_id=coupon.id,
        customer_profile_id=profile.id,
        order_id=uuid.uuid4(),
        discount_amount_applied=100.0,
    )
    db_session.add(redemption)
    await db_session.commit()

    # Try to validate again -> should fail with usage limit reached (INV-CPN-001)
    val_payload = {
        "code": "STORE100",
        "order_amount": 400.0,
        "branch_id": str(fixture["branch_id"]),
    }
    resp = await client.post(
        "/api/v1/coupons/validate", headers=headers, json=val_payload
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "COUPON_USAGE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_create_and_list_coupons(client: AsyncClient, provision_role):
    # Create new coupon
    create_payload = {
        "code": "NEWYEAR2026",
        "discount_type": "PERCENTAGE",
        "discount_value": 20.0,
        "min_order_amount": 100.0,
        "max_redemptions_per_user": 3,
        "valid_from": datetime.now(UTC).isoformat(),
        "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "is_active": True,
    }
    admin_headers = await provision_role(
        client, "coupon-admin@example.com", "PlatformAdmin"
    )
    create_resp = await client.post(
        "/api/v1/coupons", json=create_payload, headers=admin_headers
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["code"] == "NEWYEAR2026"
    assert created_data["is_platform_coupon"] is True

    # List coupons
    list_resp = await client.get("/api/v1/coupons")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
