import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_brand_crud_flow(client: AsyncClient):
    # 1. Register merchant owner
    user_payload = {
        "email": "brandowner@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    user_res = await client.post("/api/v1/auth/register", json=user_payload)
    assert user_res.status_code == 201
    access_token = user_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Onboard merchant
    merchant_payload = {
        "business_name": "Italiano Group",
        "legal_entity_name": "Italiano Foods Pvt Ltd",
        "fssai_license_number": "11223344556677",
    }
    merchant_res = await client.post(
        "/api/v1/merchants/onboard", json=merchant_payload, headers=headers
    )
    assert merchant_res.status_code == 201
    merchant_id = merchant_res.json()["id"]

    # 3. Create Brand under Merchant (INV-BRAND-001)
    brand_payload = {
        "merchant_id": merchant_id,
        "name": "Pizza Corner",
        "logo_url": "https://cdn.saturdays.com/pizza_logo.png",
        "banner_url": "https://cdn.saturdays.com/pizza_banner.png",
        "description": "Authentic Wood-fired Pizzas",
        "cuisine_types": ["Italian", "Pizza"],
    }
    brand_res = await client.post("/api/v1/brands", json=brand_payload, headers=headers)
    assert brand_res.status_code == 201
    brand_data = brand_res.json()
    assert brand_data["name"] == "Pizza Corner"
    assert brand_data["merchant_id"] == merchant_id
    assert brand_data["cuisine_types"] == ["Italian", "Pizza"]
    brand_id = brand_data["id"]

    # 4. Get brand by ID
    get_res = await client.get(f"/api/v1/brands/{brand_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Pizza Corner"

    # 5. List brands
    list_res = await client.get(f"/api/v1/brands?merchant_id={merchant_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 6. Update brand
    update_payload = {"name": "Pizza Corner Express", "description": "Fast Gourmet Pizza"}
    update_res = await client.patch(
        f"/api/v1/brands/{brand_id}", json=update_payload, headers=headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Pizza Corner Express"

    # 7. Delete brand
    del_res = await client.delete(f"/api/v1/brands/{brand_id}", headers=headers)
    assert del_res.status_code == 204

    # 8. Fetch deleted brand should return 404
    get_del_res = await client.get(f"/api/v1/brands/{brand_id}")
    assert get_del_res.status_code == 404


@pytest.mark.asyncio
async def test_brand_invariants_and_rbac(client: AsyncClient):
    # Customer tries to create brand -> 403 Forbidden
    cust_payload = {
        "email": "custbrand@saturdays.com",
        "password": "Password123!",
        "role": "Customer",
    }
    cust_res = await client.post("/api/v1/auth/register", json=cust_payload)
    cust_headers = {"Authorization": f"Bearer {cust_res.json()['access_token']}"}

    res_cust = await client.post(
        "/api/v1/brands",
        json={"name": "Forbidden Brand"},
        headers=cust_headers,
    )
    assert res_cust.status_code == 403

    # MerchantOwner tries to create brand with non-existent merchant_id (INV-BRAND-001)
    owner_payload = {
        "email": "invalidparent@saturdays.com",
        "password": "Password123!",
        "role": "MerchantOwner",
    }
    owner_res = await client.post("/api/v1/auth/register", json=owner_payload)
    owner_headers = {"Authorization": f"Bearer {owner_res.json()['access_token']}"}

    res_invalid_parent = await client.post(
        "/api/v1/brands",
        json={
            "merchant_id": "018f3a9b-7c1d-7000-8000-000000000000",
            "name": "Orphan Brand",
        },
        headers=owner_headers,
    )
    assert res_invalid_parent.status_code == 404
    assert res_invalid_parent.json()["error_code"] == "MERCHANT_NOT_FOUND"
