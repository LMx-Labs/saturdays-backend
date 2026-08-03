import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_branch_crud_flow(client: AsyncClient):
    # 1. Register merchant owner
    user_payload = {
        "email": "branchowner@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    user_res = await client.post("/api/v1/auth/register", json=user_payload)
    assert user_res.status_code == 201
    access_token = user_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Onboard merchant & brand
    merchant_res = await client.post(
        "/api/v1/merchants/onboard",
        json={
            "business_name": "Burger Empire",
            "legal_entity_name": "Burger Empire Pvt Ltd",
            "fssai_license_number": "99887766554433",
        },
        headers=headers,
    )
    merchant_id = merchant_res.json()["id"]

    brand_res = await client.post(
        "/api/v1/brands",
        json={"merchant_id": merchant_id, "name": "Burger Shack"},
        headers=headers,
    )
    brand_id = brand_res.json()["id"]

    # 3. Create branch under Brand (INV-BRANCH-001)
    branch_payload = {
        "brand_id": brand_id,
        "name": "Burger Shack VIT Main Campus",
        "address_text": "Food Court Block 2, VIT Campus",
        "latitude": 12.9692,
        "longitude": 79.1559,
        "opening_time": "09:00:00",
        "closing_time": "22:00:00",
    }
    branch_res = await client.post(
        "/api/v1/branches", json=branch_payload, headers=headers
    )
    assert branch_res.status_code == 201
    branch_data = branch_res.json()
    assert branch_data["name"] == "Burger Shack VIT Main Campus"
    assert branch_data["brand_id"] == brand_id
    assert branch_data["is_active"] is True
    assert branch_data["opening_time"] == "09:00:00"
    assert branch_data["closing_time"] == "22:00:00"
    branch_id = branch_data["id"]

    # 4. Get branch by ID
    get_res = await client.get(f"/api/v1/branches/{branch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Burger Shack VIT Main Campus"

    # 5. List branches by brand_id
    list_res = await client.get(f"/api/v1/branches?brand_id={brand_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 6. Toggle branch status (INV-0006 ONLINE/OFFLINE toggle)
    status_res = await client.patch(
        f"/api/v1/branches/{branch_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

    # 7. Update branch details
    update_res = await client.patch(
        f"/api/v1/branches/{branch_id}",
        json={"name": "Burger Shack VIT Main Canteen", "is_active": True},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Burger Shack VIT Main Canteen"
    assert update_res.json()["is_active"] is True

    # 8. Soft delete branch
    del_res = await client.delete(f"/api/v1/branches/{branch_id}", headers=headers)
    assert del_res.status_code == 204

    # 9. Get deleted branch returns 404
    get_del = await client.get(f"/api/v1/branches/{branch_id}")
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_branch_invariants_and_rbac(client: AsyncClient):
    # Customer tries to create branch -> 403 Forbidden
    cust_payload = {
        "email": "custbranch@saturdays.com",
        "password": "Password123!",
        "role": "Customer",
    }
    cust_res = await client.post("/api/v1/auth/register", json=cust_payload)
    cust_headers = {"Authorization": f"Bearer {cust_res.json()['access_token']}"}

    res_cust = await client.post(
        "/api/v1/branches",
        json={
            "brand_id": "018f3a9b-7c1d-7000-8000-000000000000",
            "name": "Forbidden Branch",
            "address_text": "Invalid Address",
        },
        headers=cust_headers,
    )
    assert res_cust.status_code == 403

    # BranchManager tries to create branch under non-existent brand (INV-BRANCH-001)
    mgr_payload = {
        "email": "mgrbranch@saturdays.com",
        "password": "Password123!",
        "role": "BranchManager",
    }
    mgr_res = await client.post("/api/v1/auth/register", json=mgr_payload)
    mgr_headers = {"Authorization": f"Bearer {mgr_res.json()['access_token']}"}

    res_orphan = await client.post(
        "/api/v1/branches",
        json={
            "brand_id": "018f3a9b-7c1d-7000-8000-000000000000",
            "name": "Orphan Branch",
            "address_text": "Orphan Street",
        },
        headers=mgr_headers,
    )
    assert res_orphan.status_code == 404
    assert res_orphan.json()["error_code"] == "BRAND_NOT_FOUND"
