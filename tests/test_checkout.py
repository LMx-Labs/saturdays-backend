from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.cart.models import Cart, CartItem
from app.core.security import hash_password
from app.coupon.models import Coupon
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.fixture
async def setup_checkout_fixture(db_session: AsyncSession):
    # Customer
    cust_user = User(
        email="checkoutcust@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(cust_user)
    await db_session.flush()

    profile = CustomerProfile(user_id=cust_user.id, full_name="Checkout User")
    db_session.add(profile)
    await db_session.flush()

    # Merchant, Brand, Branch, Kitchen
    merchant = Merchant(
        owner_user_id=cust_user.id,
        business_name="Checkout Store",
        legal_entity_name="Checkout LLC",
        fssai_license_number="12345678901234",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Checkout Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id,
        name="Checkout Branch",
        address_text="Checkout Street 1",
        is_active=True,
    )
    db_session.add(branch)
    await db_session.flush()

    kitchen = Kitchen(branch_id=branch.id, name="Main Kitchen", is_active=True)
    db_session.add(kitchen)
    await db_session.flush()

    # Menu & Menu Item
    menu = Menu(branch_id=branch.id, name="Checkout Menu", is_active=True)
    db_session.add(menu)
    await db_session.flush()

    category = MenuCategory(menu_id=menu.id, name="Main Dishes")
    db_session.add(category)
    await db_session.flush()

    menu_item = MenuItem(
        category_id=category.id,
        name="Gourmet Burger",
        base_price=200.00,
        is_available=True,
    )
    db_session.add(menu_item)
    await db_session.flush()

    # Inventory item
    inv_item = InventoryItem(
        branch_id=branch.id,
        menu_item_id=menu_item.id,
        quantity=50,
        is_in_stock=True,
    )
    db_session.add(inv_item)
    await db_session.flush()

    # Cart & CartItem
    cart = Cart(customer_profile_id=profile.id, branch_id=branch.id)
    db_session.add(cart)
    await db_session.flush()

    cart_item = CartItem(
        cart_id=cart.id,
        menu_item_id=menu_item.id,
        quantity=2,
    )
    db_session.add(cart_item)
    await db_session.flush()

    # Coupon
    now = datetime.now(UTC)
    coupon = Coupon(
        code="SAVE50",
        discount_type="FLAT",
        discount_value=50.00,
        min_order_amount=100.00,
        max_discount_amount=50.00,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=10),
        is_active=True,
    )
    db_session.add(coupon)
    await db_session.commit()

    return {
        "cust_user": cust_user,
        "profile": profile,
        "branch": branch,
        "kitchen": kitchen,
        "menu_item": menu_item,
        "inv_item": inv_item,
        "cart": cart,
        "cart_id": str(cart.id),
        "coupon_code": "SAVE50",
    }


@pytest.mark.asyncio
async def test_checkout_validation_success(
    client: AsyncClient, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    # Login customer
    user_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ctx["cust_user"].email, "password": "Password123!"},
    )
    headers = {"Authorization": f"Bearer {user_res.json()['access_token']}"}

    payload = {
        "cart_id": ctx["cart_id"],
        "coupon_code": ctx["coupon_code"],
    }
    res = await client.post("/api/v1/checkout/validate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["subtotal"] == 400.00  # 2 * 200.00
    assert data["tax_amount"] == 20.00  # 5% GST of 400.00
    assert data["delivery_fee"] == 30.00
    assert data["discount_amount"] == 50.00
    assert data["final_payable_amount"] == 400.00 + 20.00 + 30.00 - 50.00  # 400.00
    assert len(data["issues"]) == 0


@pytest.mark.asyncio
async def test_checkout_summary_endpoint(
    client: AsyncClient, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    user_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ctx["cust_user"].email, "password": "Password123!"},
    )
    headers = {"Authorization": f"Bearer {user_res.json()['access_token']}"}

    payload = {"cart_id": ctx["cart_id"]}
    res = await client.post("/api/v1/checkout/summary", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["subtotal"] == 400.00
    assert data["discount_amount"] == 0.00
    assert data["final_payable_amount"] == 450.00  # 400 + 20 + 30


@pytest.mark.asyncio
async def test_checkout_branch_closed_invariant(
    client: AsyncClient, db_session: AsyncSession, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    # Set branch offline
    branch = ctx["branch"]
    branch.is_active = False
    await db_session.commit()

    user_res = await client.post(
        "/api/v1/auth/login",
        json={"email": ctx["cust_user"].email, "password": "Password123!"},
    )
    headers = {"Authorization": f"Bearer {user_res.json()['access_token']}"}

    payload = {"cart_id": ctx["cart_id"]}
    res = await client.post("/api/v1/checkout/validate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert any(i["code"] == "BRANCH_OFFLINE" for i in data["issues"])
