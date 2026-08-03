import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_merchant_onboarding_and_profile_flow(client: AsyncClient):
    # 1. Register a MerchantOwner user
    user_payload = {
        "email": "owner1@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    user_res = await client.post("/api/v1/auth/register", json=user_payload)
    assert user_res.status_code == 201
    access_token = user_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Onboard merchant profile
    onboard_payload = {
        "business_name": "Taco Fiesta",
        "legal_entity_name": "Taco Fiesta Foods Pvt Ltd",
        "fssai_license_number": "12345678901234",
        "gstin": "29ABCDE1234F1Z5",
        "bank_account_number": "987654321012",
        "bank_ifsc_code": "SBIN0001234",
    }
    res = await client.post(
        "/api/v1/merchants/onboard", json=onboard_payload, headers=headers
    )
    assert res.status_code == 201
    data = res.json()
    assert data["business_name"] == "Taco Fiesta"
    assert data["legal_entity_name"] == "Taco Fiesta Foods Pvt Ltd"
    assert data["fssai_license_number"] == "12345678901234"
    assert data["gstin"] == "29ABCDE1234F1Z5"
    assert data["status"] == "DRAFT"
    merchant_id = data["id"]

    # 3. Fetch current merchant profile
    me_res = await client.get("/api/v1/merchants/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == merchant_id

    # 4. Fetch merchant by ID
    get_id_res = await client.get(f"/api/v1/merchants/{merchant_id}", headers=headers)
    assert get_id_res.status_code == 200
    assert get_id_res.json()["business_name"] == "Taco Fiesta"


@pytest.mark.asyncio
async def test_merchant_validation_and_duplicate_checks(client: AsyncClient):
    user_payload = {
        "email": "owner2@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    user_res = await client.post("/api/v1/auth/register", json=user_payload)
    access_token = user_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Invalid FSSAI license number (must be 14 digits)
    invalid_fssai_payload = {
        "business_name": "Bad FSSAI Store",
        "legal_entity_name": "Bad FSSAI Pvt Ltd",
        "fssai_license_number": "12345",
    }
    res_fssai = await client.post(
        "/api/v1/merchants/onboard", json=invalid_fssai_payload, headers=headers
    )
    assert res_fssai.status_code == 422

    # Valid onboarding
    valid_payload = {
        "business_name": "Good Store",
        "legal_entity_name": "Good Store Pvt Ltd",
        "fssai_license_number": "11112222333344",
        "gstin": "27AAAAA0000A1Z5",
    }
    res_valid = await client.post(
        "/api/v1/merchants/onboard", json=valid_payload, headers=headers
    )
    assert res_valid.status_code == 201

    # Duplicate merchant for same user
    res_dup_user = await client.post(
        "/api/v1/merchants/onboard", json=valid_payload, headers=headers
    )
    assert res_dup_user.status_code == 409
    assert res_dup_user.json()["error_code"] == "MERCHANT_ALREADY_EXISTS"

    # Duplicate GSTIN check for another user
    user2_payload = {
        "email": "owner3@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    user2_res = await client.post("/api/v1/auth/register", json=user2_payload)
    access_token2 = user2_res.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {access_token2}"}

    dup_gstin_payload = {
        "business_name": "Another Store",
        "legal_entity_name": "Another Store Pvt Ltd",
        "fssai_license_number": "99998888777766",
        "gstin": "27AAAAA0000A1Z5",  # Duplicate GSTIN
    }
    res_dup_gstin = await client.post(
        "/api/v1/merchants/onboard", json=dup_gstin_payload, headers=headers2
    )
    assert res_dup_gstin.status_code == 409
    assert res_dup_gstin.json()["error_code"] == "DUPLICATE_GSTIN"


@pytest.mark.asyncio
async def test_merchant_status_lifecycle_and_rbac(client: AsyncClient):
    # Register admin and merchant owner
    admin_payload = {
        "email": "admin@saturdays.com",
        "password": "Password123!",
        "role": "PlatformAdmin",
    }
    admin_res = await client.post("/api/v1/auth/register", json=admin_payload)
    admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

    owner_payload = {
        "email": "owner4@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    owner_res = await client.post("/api/v1/auth/register", json=owner_payload)
    owner_headers = {"Authorization": f"Bearer {owner_res.json()['access_token']}"}

    customer_payload = {
        "email": "customer1@saturdays.com",
        "password": "Password123!",
        "role": "Customer",
    }
    customer_res = await client.post("/api/v1/auth/register", json=customer_payload)
    customer_headers = {
        "Authorization": f"Bearer {customer_res.json()['access_token']}"
    }

    # Customer cannot onboard merchant
    res_cust = await client.post(
        "/api/v1/merchants/onboard",
        json={
            "business_name": "Unauthorized",
            "legal_entity_name": "Unauthorized",
            "fssai_license_number": "12345678901234",
        },
        headers=customer_headers,
    )
    assert res_cust.status_code == 403

    # Owner onboards
    res_onboard = await client.post(
        "/api/v1/merchants/onboard",
        json={
            "business_name": "Lifecycle Store",
            "legal_entity_name": "Lifecycle Store Pvt Ltd",
            "fssai_license_number": "55556666777788",
        },
        headers=owner_headers,
    )
    merchant_id = res_onboard.json()["id"]

    # Non-admin cannot update status
    res_owner_status = await client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        json={"status": "APPROVED"},
        headers=owner_headers,
    )
    assert res_owner_status.status_code == 403

    # Admin updates status: DRAFT -> PENDING_VERIFICATION -> APPROVED
    res_s1 = await client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        json={"status": "PENDING_VERIFICATION"},
        headers=admin_headers,
    )
    assert res_s1.status_code == 200
    assert res_s1.json()["status"] == "PENDING_VERIFICATION"

    res_s2 = await client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        json={"status": "APPROVED"},
        headers=admin_headers,
    )
    assert res_s2.status_code == 200
    assert res_s2.json()["status"] == "APPROVED"

    # Invalid status transition: APPROVED -> DRAFT (Not allowed)
    res_invalid_trans = await client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        json={"status": "DRAFT"},
        headers=admin_headers,
    )
    assert res_invalid_trans.status_code == 400
    assert res_invalid_trans.json()["error_code"] == "INVALID_STATUS_TRANSITION"
