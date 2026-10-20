import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import seed_user_login


@pytest.mark.asyncio
async def test_kitchen_crud_flow(client: AsyncClient, db_session: AsyncSession):
    owner = await seed_user_login(
        client, db_session, email="kitchenowner@saturdays.com", role="MerchantOwner"
    )
    owner_headers = owner["headers"]

    # 2. Setup Merchant -> Brand -> Branch hierarchy
    merchant_res = await client.post(
        "/api/v1/merchants/onboard",
        json={
            "business_name": "Kitchen Group",
            "legal_entity_name": "Kitchen Foods Pvt Ltd",
            "fssai_license_number": "12312312312312",
        },
        headers=owner_headers,
    )
    merchant_id = merchant_res.json()["id"]

    brand_res = await client.post(
        "/api/v1/brands",
        json={"merchant_id": merchant_id, "name": "Bistro Kitchens"},
        headers=owner_headers,
    )
    brand_id = brand_res.json()["id"]

    branch_res = await client.post(
        "/api/v1/branches",
        json={
            "brand_id": brand_id,
            "name": "Bistro Main Branch",
            "address_text": "Central Avenue 101",
        },
        headers=owner_headers,
    )
    branch_id = branch_res.json()["id"]

    # 3. Create Kitchen unit under Branch (INV-KITCH-001)
    kitchen_payload = {
        "branch_id": branch_id,
        "name": "Hot Kitchen Station 1",
        "is_active": True,
    }
    kitchen_res = await client.post(
        "/api/v1/kitchens", json=kitchen_payload, headers=owner_headers
    )
    assert kitchen_res.status_code == 201
    k_data = kitchen_res.json()
    assert k_data["name"] == "Hot Kitchen Station 1"
    assert k_data["branch_id"] == branch_id
    assert k_data["is_active"] is True
    kitchen_id = k_data["id"]

    # 4. Get kitchen by ID
    get_res = await client.get(f"/api/v1/kitchens/{kitchen_id}", headers=owner_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Hot Kitchen Station 1"

    # 5. List branch kitchens
    list_res = await client.get(
        f"/api/v1/branches/{branch_id}/kitchens", headers=owner_headers
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 6. Update kitchen details
    update_res = await client.patch(
        f"/api/v1/kitchens/{kitchen_id}",
        json={"name": "Hot Kitchen Main Line", "is_active": True},
        headers=owner_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Hot Kitchen Main Line"

    # 7. Soft delete kitchen
    del_res = await client.delete(
        f"/api/v1/kitchens/{kitchen_id}", headers=owner_headers
    )
    assert del_res.status_code == 204

    # 8. Fetch deleted kitchen returns 404
    get_del = await client.get(f"/api/v1/kitchens/{kitchen_id}", headers=owner_headers)
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_kitchen_invariants_and_rbac(
    client: AsyncClient, db_session: AsyncSession
):
    # Customer tries to create kitchen -> 403 Forbidden
    cust_payload = {
        "email": "custkitchen@saturdays.com",
        "password": "Password123!",
        "role": "Customer",
    }
    cust_res = await client.post("/api/v1/auth/register", json=cust_payload)
    cust_headers = {"Authorization": f"Bearer {cust_res.json()['access_token']}"}

    res_cust = await client.post(
        "/api/v1/kitchens",
        json={
            "branch_id": "018f3a9b-7c1d-7000-8000-000000000000",
            "name": "Forbidden Kitchen",
        },
        headers=cust_headers,
    )
    assert res_cust.status_code == 403

    # BranchManager tries to create kitchen under non-existent branch_id (INV-KITCH-001)
    mgr = await seed_user_login(
        client, db_session, email="mgrkitchen@saturdays.com", role="BranchManager"
    )
    mgr_headers = mgr["headers"]

    res_orphan = await client.post(
        "/api/v1/kitchens",
        json={
            "branch_id": "018f3a9b-7c1d-7000-8000-000000000000",
            "name": "Orphan Kitchen",
        },
        headers=mgr_headers,
    )
    assert res_orphan.status_code == 404
    assert res_orphan.json()["error_code"] == "BRANCH_NOT_FOUND"
