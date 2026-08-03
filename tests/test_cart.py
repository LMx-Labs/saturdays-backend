import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.cart.models import Cart
from app.core.security import hash_password
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.fixture
async def setup_cart_fixture(db_session: AsyncSession):
    # Create customer user
    cust_user = User(
        email="cart_user@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(cust_user)
    await db_session.flush()

    # Create merchant & brand
    merchant = Merchant(
        owner_user_id=cust_user.id,
        business_name="Cart Merchant",
        legal_entity_name="Cart Merchant LLC",
        fssai_license_number="12345678901234",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Cart Brand")
    db_session.add(brand)
    await db_session.flush()

    # Create Branch A and Branch B
    branch_a = Branch(brand_id=brand.id, name="Branch Alpha", address_text="Alpha Street")
    branch_b = Branch(brand_id=brand.id, name="Branch Beta", address_text="Beta Street")
    db_session.add_all([branch_a, branch_b])
    await db_session.flush()

    # Create Menu & Menu Items for Branch A
    menu_a = Menu(branch_id=branch_a.id, name="Menu Alpha", is_active=True)
    db_session.add(menu_a)
    await db_session.flush()

    cat_a = MenuCategory(menu_id=menu_a.id, name="Category Alpha")
    db_session.add(cat_a)
    await db_session.flush()

    item_available = MenuItem(
        category_id=cat_a.id, name="Burger", base_price=150.00, is_available=True
    )
    item_unavailable = MenuItem(
        category_id=cat_a.id,
        name="Out of Stock Pizza",
        base_price=250.00,
        is_available=False,
    )
    db_session.add_all([item_available, item_unavailable])

    # Create Menu Item for Branch B
    menu_b = Menu(branch_id=branch_b.id, name="Menu Beta", is_active=True)
    db_session.add(menu_b)
    await db_session.flush()

    cat_b = MenuCategory(menu_id=menu_b.id, name="Category Beta")
    db_session.add(cat_b)
    await db_session.flush()

    item_b = MenuItem(category_id=cat_b.id, name="Beta Taco", base_price=100.00, is_available=True)
    db_session.add(item_b)

    await db_session.commit()

    return {
        "cust_user": cust_user,
        "branch_a_id": str(branch_a.id),
        "branch_b_id": str(branch_b.id),
        "item_available_id": str(item_available.id),
        "item_unavailable_id": str(item_unavailable.id),
        "item_b_id": str(item_b.id),
        "branch_a": branch_a,
        "branch_b": branch_b,
        "item_available": item_available,
        "item_unavailable": item_unavailable,
        "item_b": item_b,
    }


async def get_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_cart_add_and_update_items(client: AsyncClient, setup_cart_fixture: dict):
    fixture = setup_cart_fixture
    headers = await get_headers(client, fixture["cust_user"].email)

    # First access to customer profile
    await client.get("/api/v1/customers/me", headers=headers)

    # Add available item
    add_payload = {
        "branch_id": str(fixture["branch_a"].id),
        "menu_item_id": str(fixture["item_available"].id),
        "quantity": 2,
    }
    resp = await client.post("/api/v1/cart/items", headers=headers, json=add_payload)
    assert resp.status_code == 200
    cart_data = resp.json()
    assert cart_data["total_items"] == 2
    assert cart_data["subtotal"] == 300.00
    assert len(cart_data["items"]) == 1

    item_id = cart_data["items"][0]["id"]

    # Update item quantity to 5
    up_resp = await client.put(
        f"/api/v1/cart/items/{item_id}",
        headers=headers,
        json={"quantity": 5},
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["total_items"] == 5
    assert up_resp.json()["subtotal"] == 750.00

    # Update item quantity to 0 (removes item)
    zero_resp = await client.put(
        f"/api/v1/cart/items/{item_id}",
        headers=headers,
        json={"quantity": 0},
    )
    assert zero_resp.status_code == 200
    assert zero_resp.json()["total_items"] == 0


@pytest.mark.asyncio
async def test_cart_single_branch_constraint(client: AsyncClient, setup_cart_fixture: dict):
    fixture = setup_cart_fixture
    headers = await get_headers(client, fixture["cust_user"].email)
    await client.get("/api/v1/customers/me", headers=headers)

    # Add item from Branch A
    await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "branch_id": fixture["branch_a_id"],
            "menu_item_id": fixture["item_available_id"],
            "quantity": 1,
        },
    )

    # Attempt to add item from Branch B (INV-CART-001)
    conflict_resp = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "branch_id": fixture["branch_b_id"],
            "menu_item_id": fixture["item_b_id"],
            "quantity": 1,
        },
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error_code"] == "CROSS_BRANCH_CART_CONFLICT"


@pytest.mark.asyncio
async def test_cart_availability_checks_and_validation(
    client: AsyncClient, setup_cart_fixture: dict
):
    fixture = setup_cart_fixture
    headers = await get_headers(client, fixture["cust_user"].email)
    await client.get("/api/v1/customers/me", headers=headers)

    # Attempt to add unavailable item
    unavail_resp = await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "branch_id": str(fixture["branch_a"].id),
            "menu_item_id": str(fixture["item_unavailable"].id),
            "quantity": 1,
        },
    )
    assert unavail_resp.status_code == 422
    assert unavail_resp.json()["error_code"] == "ITEM_UNAVAILABLE"

    # Add available item
    await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "branch_id": str(fixture["branch_a"].id),
            "menu_item_id": str(fixture["item_available"].id),
            "quantity": 1,
        },
    )

    # Validate cart
    val_resp = await client.post("/api/v1/cart/validate", headers=headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True
    assert val_data["subtotal"] == 150.00


@pytest.mark.asyncio
async def test_cart_expiry_and_purge(
    client: AsyncClient, setup_cart_fixture: dict, db_session: AsyncSession
):
    fixture = setup_cart_fixture
    headers = await get_headers(client, fixture["cust_user"].email)
    cust_resp = await client.get("/api/v1/customers/me", headers=headers)
    cust_profile_id = uuid.UUID(cust_resp.json()["id"])

    # Manually insert a cart updated 8 days ago
    old_cart = Cart(
        customer_profile_id=cust_profile_id,
        branch_id=fixture["branch_a"].id,
        updated_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(old_cart)
    await db_session.commit()

    # Call purge endpoint
    purge_resp = await client.delete("/api/v1/cart/purge-expired", params={"max_age_days": 7})
    assert purge_resp.status_code == 200
    assert purge_resp.json()["purged_count"] >= 1
