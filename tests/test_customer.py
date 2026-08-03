import uuid

import pytest
from httpx import AsyncClient


async def get_authenticated_headers(
    client: AsyncClient, email: str = "customer@saturdays.com"
) -> dict:
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "role": "Customer"},
    )
    token = reg_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_and_update_customer_profile(client: AsyncClient):
    headers = await get_authenticated_headers(client, "profile_test@saturdays.com")

    # Get profile (auto-initialized)
    get_resp = await client.get("/api/v1/customers/me", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["full_name"] == "Customer"

    # Update profile
    put_resp = await client.put(
        "/api/v1/customers/me",
        headers=headers,
        json={"full_name": "Jane Doe", "phone_number": "+1234567890"},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["full_name"] == "Jane Doe"
    assert updated["phone_number"] == "+1234567890"


@pytest.mark.asyncio
async def test_customer_address_primary_invariants(client: AsyncClient):
    headers = await get_authenticated_headers(client, "address_test@saturdays.com")

    # Add first address (should automatically become primary)
    addr1_payload = {
        "address_line": "123 Main St",
        "building_name": "Block A",
        "campus_zone": "Men's Hostel Phase 1",
        "is_primary": False,
    }
    resp1 = await client.post("/api/v1/customers/me/addresses", headers=headers, json=addr1_payload)
    assert resp1.status_code == 201
    addr1 = resp1.json()
    assert addr1["is_primary"] is True  # INV-CUST-002: First address forced primary

    # Add second address as non-primary
    addr2_payload = {
        "address_line": "456 Side St",
        "building_name": "Block B",
        "campus_zone": "Men's Hostel Phase 2",
        "is_primary": False,
    }
    resp2 = await client.post("/api/v1/customers/me/addresses", headers=headers, json=addr2_payload)
    assert resp2.status_code == 201
    addr2 = resp2.json()
    assert addr2["is_primary"] is False

    # Set second address as primary
    resp_pri = await client.put(
        f"/api/v1/customers/me/addresses/{addr2['id']}/primary", headers=headers
    )
    assert resp_pri.status_code == 200
    assert resp_pri.json()["is_primary"] is True

    # List addresses: addr2 should be primary, addr1 should now be non-primary
    list_resp = await client.get("/api/v1/customers/me/addresses", headers=headers)
    assert list_resp.status_code == 200
    addresses = list_resp.json()
    primary_count = sum(1 for a in addresses if a["is_primary"])
    assert primary_count == 1  # INV-CUST-002: Exactly one primary address

    # Delete primary address (addr2), remaining address (addr1) should automatically become primary
    del_resp = await client.delete(f"/api/v1/customers/me/addresses/{addr2['id']}", headers=headers)
    assert del_resp.status_code == 204

    list_resp2 = await client.get("/api/v1/customers/me/addresses", headers=headers)
    assert list_resp2.status_code == 200
    remaining_addresses = list_resp2.json()
    assert len(remaining_addresses) == 1
    assert remaining_addresses[0]["id"] == addr1["id"]
    assert remaining_addresses[0]["is_primary"] is True


@pytest.mark.asyncio
async def test_customer_favorite_branch_invariants(client: AsyncClient):
    headers = await get_authenticated_headers(client, "fav_test@saturdays.com")
    branch_id = str(uuid.uuid4())

    # Add favorite
    add_resp = await client.post(
        "/api/v1/customers/me/favorites", headers=headers, json={"branch_id": branch_id}
    )
    assert add_resp.status_code == 201
    fav = add_resp.json()
    assert fav["branch_id"] == branch_id

    # Add duplicate favorite (should fail with 409 Conflict - INV-CUST-003)
    dup_resp = await client.post(
        "/api/v1/customers/me/favorites", headers=headers, json={"branch_id": branch_id}
    )
    assert dup_resp.status_code == 409

    # List favorites
    list_resp = await client.get("/api/v1/customers/me/favorites", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Remove favorite
    del_resp = await client.delete(f"/api/v1/customers/me/favorites/{branch_id}", headers=headers)
    assert del_resp.status_code == 204

    # List favorites after removal
    list_resp2 = await client.get("/api/v1/customers/me/favorites", headers=headers)
    assert list_resp2.status_code == 200
    assert len(list_resp2.json()) == 0
