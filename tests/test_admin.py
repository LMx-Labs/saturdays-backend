import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import settings
from app.core.security import hash_password
from app.merchant.models import Merchant
from app.subscription.models import MerchantSubscription


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

    db_session.add_all([admin_user, merchant_user])
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=merchant_user.id,
        business_name="Pending Onboarding Store",
        legal_entity_name="Pending Store LLC",
        fssai_license_number="12345678901234",
        status="PENDING",
    )
    db_session.add(merchant)
    await db_session.commit()

    return {"admin_user": admin_user, "merchant": merchant}


async def get_admin_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_merchant_approval_and_audit(
    client: AsyncClient, setup_admin_fixture: dict
):
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
async def test_admin_banner_cms_and_feature_flags(
    client: AsyncClient, setup_admin_fixture: dict
):
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
    banner_resp = await client.post(
        "/api/v1/admin/banners", headers=headers, json=banner_payload
    )
    assert banner_resp.status_code == 201
    banner_id = banner_resp.json()["id"]

    # 2. List banners
    list_resp = await client.get("/api/v1/admin/banners")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 3. Delete banner
    del_resp = await client.delete(
        f"/api/v1/admin/banners/{banner_id}", headers=headers
    )
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
    client: AsyncClient, setup_admin_fixture: dict, monkeypatch
):
    monkeypatch.setattr(settings, "REFUNDS_ENABLED", True)
    fixture = setup_admin_fixture
    headers = await get_admin_headers(client, fixture["admin_user"].email)

    # Refund override
    ref_payload = {
        "payment_id": str(uuid.uuid4()),
        "amount": 250.0,
        "reason": "Customer complaint dispute resolution",
    }
    ref_resp = await client.post(
        "/api/v1/admin/refunds/override", headers=headers, json=ref_payload
    )
    assert ref_resp.status_code == 200
    assert ref_resp.json()["status"] == "PROCESSED"

    # Analytics overview
    analytics_resp = await client.get(
        "/api/v1/admin/analytics/overview", headers=headers
    )
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert "total_merchants" in data
    assert "gross_revenue" in data


@pytest.mark.asyncio
async def test_admin_refund_override_blocked_by_policy(
    client: AsyncClient, setup_admin_fixture: dict
):
    headers = await get_admin_headers(client, setup_admin_fixture["admin_user"].email)
    resp = await client.post(
        "/api/v1/admin/refunds/override",
        headers=headers,
        json={"payment_id": str(uuid.uuid4()), "amount": 10.0, "reason": "x"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "REFUNDS_DISABLED_USE_STORE_CREDIT"


@pytest.mark.asyncio
async def test_admin_set_password_by_user_id(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    # 1. Register a customer user
    cust_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "target_customer@saturdays.com",
            "password": "OriginalPassword123!",
            "role": "Customer",
        },
    )
    assert cust_res.status_code == 201
    user_id = cust_res.json()["user"]["id"]

    # 2. Admin overrides target user's password via /set-password
    new_admin_pwd = "AdminSetSecret123!"
    set_resp = await client.post(
        "/api/v1/admin/set-password",
        headers=admin_headers,
        json={"user_id": user_id, "password": new_admin_pwd},
    )
    assert set_resp.status_code == 200
    assert "Password has been successfully updated" in set_resp.json()["message"]

    # 3. Target user can log in with new password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "target_customer@saturdays.com", "password": new_admin_pwd},
    )
    assert login_resp.status_code == 200

    # 4. Old password fails
    old_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "target_customer@saturdays.com",
            "password": "OriginalPassword123!",
        },
    )
    assert old_login.status_code == 401

    # 5. Verify audit log entry
    audit_resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    actions = [log["action"] for log in audit_resp.json()]
    assert "USER_PASSWORD_SET_BY_ADMIN" in actions


@pytest.mark.asyncio
async def test_admin_set_password_by_email(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    target_email = "target_by_email@saturdays.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": target_email,
            "password": "InitialPassword123!",
            "role": "Customer",
        },
    )

    new_pwd = "ChangedViaAdminByEmail123!"
    set_resp = await client.post(
        "/api/v1/admin/set-password",
        headers=admin_headers,
        json={"email": target_email, "new_password": new_pwd},
    )
    assert set_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": new_pwd},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_access_set_password(
    client: AsyncClient, setup_admin_fixture: dict
):
    # Customer attempts to set password
    cust_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "unauthorized_user@saturdays.com",
            "password": "Password123!",
            "role": "Customer",
        },
    )
    cust_token = cust_res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    resp = await client.post(
        "/api/v1/admin/set-password",
        headers=cust_headers,
        json={"user_id": str(uuid.uuid4()), "password": "HackedPassword123!"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "ROLE_NOT_AUTHORIZED"


@pytest.mark.asyncio
async def test_admin_set_password_user_not_found(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    resp = await client.post(
        "/api/v1/admin/set-password",
        headers=admin_headers,
        json={"user_id": str(uuid.uuid4()), "password": "SomeValidPassword123!"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_list_and_filter_subscriptions(
    client: AsyncClient, setup_admin_fixture: dict, db_session: AsyncSession
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    # Seed an active BASIC subscription
    now = datetime.now(UTC)
    sub = MerchantSubscription(
        merchant_id=merchant.id,
        plan_tier="BASIC",
        billing_cycle="MONTHLY",
        status="ACTIVE",
        commission_rate_percentage=5.00,
        valid_until=now + timedelta(days=30),
    )
    db_session.add(sub)
    await db_session.commit()

    # List all subscriptions
    resp = await client.get("/api/v1/admin/subscriptions", headers=admin_headers)
    assert resp.status_code == 200
    subs = resp.json()
    assert len(subs) >= 1
    found = next((s for s in subs if s["id"] == str(sub.id)), None)
    assert found is not None
    assert found["merchant_id"] == str(merchant.id)
    assert found["business_name"] == merchant.business_name
    assert found["plan_tier"] == "BASIC"
    assert found["commission_rate_percentage"] == 5.0
    assert found["max_branches"] == 1

    # Filter by plan_tier
    tier_resp = await client.get(
        "/api/v1/admin/subscriptions?plan_tier=BASIC", headers=admin_headers
    )
    assert tier_resp.status_code == 200
    assert any(s["id"] == str(sub.id) for s in tier_resp.json())

    # Filter by non-existent tier
    empty_resp = await client.get(
        "/api/v1/admin/subscriptions?plan_tier=NON_EXISTENT", headers=admin_headers
    )
    assert empty_resp.status_code == 200
    assert len(empty_resp.json()) == 0


@pytest.mark.asyncio
async def test_admin_subscription_history(
    client: AsyncClient, setup_admin_fixture: dict, db_session: AsyncSession
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    now = datetime.now(UTC)
    sub1 = MerchantSubscription(
        merchant_id=merchant.id,
        plan_tier="BASIC",
        billing_cycle="MONTHLY",
        status="SUPERSEDED",
        commission_rate_percentage=5.00,
        valid_until=now - timedelta(days=1),
        created_at=now - timedelta(days=30),
    )
    sub2 = MerchantSubscription(
        merchant_id=merchant.id,
        plan_tier="PROFESSIONAL",
        billing_cycle="MONTHLY",
        status="ACTIVE",
        commission_rate_percentage=3.50,
        valid_until=now + timedelta(days=30),
        created_at=now,
    )
    db_session.add_all([sub1, sub2])
    await db_session.commit()

    # Get history via merchant-scoped endpoint
    m_resp = await client.get(
        f"/api/v1/admin/merchants/{merchant.id}/subscriptions",
        headers=admin_headers,
    )
    assert m_resp.status_code == 200
    history = m_resp.json()
    assert len(history) == 2
    # Verify chronological descending order (sub2 was created after sub1)
    assert history[0]["id"] == str(sub2.id)
    assert history[1]["id"] == str(sub1.id)

    # Get history via query parameter endpoint
    h_resp = await client.get(
        f"/api/v1/admin/subscriptions/history?merchant_id={merchant.id}",
        headers=admin_headers,
    )
    assert h_resp.status_code == 200
    assert len(h_resp.json()) == 2


@pytest.mark.asyncio
async def test_admin_modify_subscription_by_id(
    client: AsyncClient, setup_admin_fixture: dict, db_session: AsyncSession
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    now = datetime.now(UTC)
    sub = MerchantSubscription(
        merchant_id=merchant.id,
        plan_tier="BASIC",
        billing_cycle="MONTHLY",
        status="ACTIVE",
        commission_rate_percentage=5.00,
        valid_until=now + timedelta(days=30),
    )
    db_session.add(sub)
    await db_session.commit()

    # Admin customizes plan tier, custom commission rate, and extends duration
    patch_resp = await client.patch(
        f"/api/v1/admin/subscriptions/{sub.id}",
        headers=admin_headers,
        json={
            "plan_tier": "ENTERPRISE",
            "commission_rate_percentage": 2.25,
            "duration_months": 6,
            "reason": "Special enterprise negotiated contract",
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["plan_tier"] == "ENTERPRISE"
    assert updated["commission_rate_percentage"] == 2.25
    assert updated["max_branches"] == -1
    assert updated["status"] == "ACTIVE"

    # Verify audit log recorded
    audit_resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    audits = audit_resp.json()
    sub_audit = next(
        (a for a in audits if a["action"] == "SUBSCRIPTION_MODIFIED"), None
    )
    assert sub_audit is not None
    assert sub_audit["target_entity_id"] == str(sub.id)


@pytest.mark.asyncio
async def test_admin_modify_merchant_subscription_endpoint(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    # Set subscription on merchant that has no existing subscription
    put_resp = await client.put(
        f"/api/v1/admin/merchants/{merchant.id}/subscription",
        headers=admin_headers,
        json={
            "plan_tier": "PROFESSIONAL",
            "billing_cycle": "ANNUAL",
            "commission_rate_percentage": 3.00,
            "reason": "Admin onboarded custom annual plan",
        },
    )
    assert put_resp.status_code == 200
    created = put_resp.json()
    assert created["merchant_id"] == str(merchant.id)
    assert created["plan_tier"] == "PROFESSIONAL"
    assert created["billing_cycle"] == "ANNUAL"
    assert created["commission_rate_percentage"] == 3.00
    assert created["max_branches"] == 5

    # Modify existing via PATCH on merchant endpoint
    patch_resp = await client.patch(
        f"/api/v1/admin/merchants/{merchant.id}/subscription",
        headers=admin_headers,
        json={"status": "SUSPENDED", "reason": "Compliance review temporary hold"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "SUSPENDED"


@pytest.mark.asyncio
async def test_admin_subscription_validation_errors(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    # Invalid plan tier
    err1 = await client.put(
        f"/api/v1/admin/merchants/{merchant.id}/subscription",
        headers=admin_headers,
        json={"plan_tier": "ULTRA_TIER"},
    )
    assert err1.status_code == 422
    assert err1.json()["error_code"] == "INVALID_PLAN_TIER"

    # Invalid billing cycle
    err2 = await client.put(
        f"/api/v1/admin/merchants/{merchant.id}/subscription",
        headers=admin_headers,
        json={"billing_cycle": "WEEKLY"},
    )
    assert err2.status_code == 422
    assert err2.json()["error_code"] == "INVALID_BILLING_CYCLE"

    # Non-existent subscription ID
    err3 = await client.patch(
        f"/api/v1/admin/subscriptions/{uuid.uuid4()}",
        headers=admin_headers,
        json={"status": "CANCELLED"},
    )
    assert err3.status_code == 404
    assert err3.json()["error_code"] == "SUBSCRIPTION_NOT_FOUND"

    # Non-existent merchant ID
    err4 = await client.get(
        f"/api/v1/admin/merchants/{uuid.uuid4()}/subscriptions",
        headers=admin_headers,
    )
    assert err4.status_code == 404
    assert err4.json()["error_code"] == "MERCHANT_NOT_FOUND"


@pytest.mark.asyncio
async def test_non_admin_cannot_access_subscription_management(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    merchant = fixture["merchant"]

    # Register customer
    cust_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer_sub_checker@saturdays.com",
            "password": "Password123!",
            "role": "Customer",
        },
    )
    cust_token = cust_res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # Customer tries to list subscriptions
    res1 = await client.get("/api/v1/admin/subscriptions", headers=cust_headers)
    assert res1.status_code == 403

    # Customer tries to modify subscription
    res2 = await client.patch(
        f"/api/v1/admin/subscriptions/{uuid.uuid4()}",
        headers=cust_headers,
        json={"plan_tier": "ENTERPRISE"},
    )
    assert res2.status_code == 403

    # Customer tries to view merchant history
    res3 = await client.get(
        f"/api/v1/admin/merchants/{merchant.id}/subscriptions",
        headers=cust_headers,
    )
    assert res3.status_code == 403


@pytest.mark.asyncio
async def test_admin_customer_crud_and_status_management(
    client: AsyncClient, setup_admin_fixture: dict
):
    fixture = setup_admin_fixture
    admin_headers = await get_admin_headers(client, fixture["admin_user"].email)

    # 1. Register two customer users
    cust1_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer_alpha@saturdays.com",
            "password": "Password123!",
            "role": "Customer",
        },
    )
    assert cust1_res.status_code == 201
    token1 = cust1_res.json()["access_token"]
    cust1_headers = {"Authorization": f"Bearer {token1}"}

    # Set profile info & an address for cust1
    await client.put(
        "/api/v1/customers/me",
        headers=cust1_headers,
        json={"full_name": "Alpha Customer", "phone_number": "+919876543210"},
    )
    await client.post(
        "/api/v1/customers/me/addresses",
        headers=cust1_headers,
        json={
            "address_line": "Alpha Dorm Room 101",
            "building_name": "Block A",
            "campus_zone": "Hostel Zone",
            "is_primary": True,
        },
    )

    cust2_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer_beta@saturdays.com",
            "password": "Password123!",
            "role": "Customer",
        },
    )
    assert cust2_res.status_code == 201
    token2 = cust2_res.json()["access_token"]
    cust2_headers = {"Authorization": f"Bearer {token2}"}
    await client.put(
        "/api/v1/customers/me",
        headers=cust2_headers,
        json={"full_name": "Beta Customer", "phone_number": "+918765432109"},
    )

    # 2. Admin lists customers
    list_res = await client.get("/api/v1/admin/customers", headers=admin_headers)
    assert list_res.status_code == 200
    customers = list_res.json()
    assert len(customers) >= 2

    # 3. Search customers by query
    search_res = await client.get(
        "/api/v1/admin/customers?search=Alpha", headers=admin_headers
    )
    assert search_res.status_code == 200
    matched = search_res.json()
    assert len(matched) == 1
    assert matched[0]["full_name"] == "Alpha Customer"
    cust1_profile_id = matched[0]["id"]

    # 4. Get customer detail (including addresses and stats)
    detail_res = await client.get(
        f"/api/v1/admin/customers/{cust1_profile_id}", headers=admin_headers
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["email"] == "customer_alpha@saturdays.com"
    assert len(detail["addresses"]) == 1
    assert detail["addresses"][0]["address_line"] == "Alpha Dorm Room 101"
    assert detail["total_orders"] == 0
    assert detail["total_spent"] == 0.0

    # 5. Update customer profile & status (toggle is_active to False, mark is_verified to True)
    update_res = await client.patch(
        f"/api/v1/admin/customers/{cust1_profile_id}",
        headers=admin_headers,
        json={
            "full_name": "Alpha Customer Renamed",
            "is_active": False,
            "is_verified": True,
        },
    )
    assert update_res.status_code == 200
    updated_detail = update_res.json()
    assert updated_detail["full_name"] == "Alpha Customer Renamed"
    assert updated_detail["is_active"] is False
    assert updated_detail["is_verified"] is True

    # Check audit log for customer update
    audit_res = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert audit_res.status_code == 200
    actions = [log["action"] for log in audit_res.json()]
    assert "CUSTOMER_UPDATED" in actions

    # 6. Filter by is_active=false
    filter_inactive = await client.get(
        "/api/v1/admin/customers?is_active=false", headers=admin_headers
    )
    assert filter_inactive.status_code == 200
    inactive_list = filter_inactive.json()
    assert any(c["id"] == cust1_profile_id for c in inactive_list)

    # 7. Non-admin RBAC check
    forbidden_list = await client.get(
        "/api/v1/admin/customers", headers=cust2_headers
    )
    assert forbidden_list.status_code == 403

    forbidden_detail = await client.get(
        f"/api/v1/admin/customers/{cust1_profile_id}", headers=cust2_headers
    )
    assert forbidden_detail.status_code == 403

    forbidden_update = await client.patch(
        f"/api/v1/admin/customers/{cust1_profile_id}",
        headers=cust2_headers,
        json={"full_name": "Unauthorized Update"},
    )
    assert forbidden_update.status_code == 403

    # 8. Customer not found
    random_id = str(uuid.uuid4())
    not_found_res = await client.get(
        f"/api/v1/admin/customers/{random_id}", headers=admin_headers
    )
    assert not_found_res.status_code == 404
    assert not_found_res.json()["error_code"] == "CUSTOMER_NOT_FOUND"

