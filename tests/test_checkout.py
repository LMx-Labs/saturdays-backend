from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.cart.models import Cart, CartItem
from app.core.security import create_access_token, hash_password
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
        status="APPROVED",
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
    branch.closing_time = branch.opening_time

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

    token = create_access_token(subject=str(cust_user.id), role=cust_user.role)
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
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_checkout_validation_success(
    client: AsyncClient, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    headers = ctx["headers"]

    payload = {
        "cart_id": ctx["cart_id"],
        "coupon_code": ctx["coupon_code"],
    }
    res = await client.post("/api/v1/checkout/validate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["subtotal"] == 400.00  # 2 * 200.00
    assert data["tax_amount"] == 0.00
    assert data["delivery_fee"] == 0.00
    assert data["discount_amount"] == 0.00
    assert data["final_payable_amount"] == 400.00
    assert any(issue["code"] == "COUPON_NOT_SUPPORTED" for issue in data["issues"])


@pytest.mark.asyncio
async def test_checkout_summary_endpoint(
    client: AsyncClient, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    headers = ctx["headers"]

    payload = {"cart_id": ctx["cart_id"]}
    res = await client.post("/api/v1/checkout/summary", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["subtotal"] == 400.00
    assert data["discount_amount"] == 0.00
    assert data["final_payable_amount"] == 400.00


@pytest.mark.asyncio
async def test_quote_and_saved_order_share_item_price(
    client: AsyncClient, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    quote = await client.post(
        "/api/v1/checkout/summary",
        json={"cart_id": ctx["cart_id"]},
        headers=ctx["headers"],
    )
    assert quote.status_code == 200
    assert quote.json()["is_valid"] is True
    order = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["menu_item"].id), "quantity": 2}],
            "delivery_address_snapshot": {"address_line": "Test"},
        },
        headers={**ctx["headers"], "Idempotency-Key": "checkout-price-case"},
    )
    assert order.status_code == 201
    assert order.json()["total_amount"] == quote.json()["final_payable_amount"]
    assert order.json()["price_breakdown_snapshot"]["subtotal"] == "400.00"


@pytest.mark.asyncio
async def test_checkout_branch_closed_invariant(
    client: AsyncClient, db_session: AsyncSession, setup_checkout_fixture: dict
):
    ctx = setup_checkout_fixture
    # Set branch offline
    branch = ctx["branch"]
    branch.is_active = False
    await db_session.commit()

    headers = ctx["headers"]

    payload = {"cart_id": ctx["cart_id"]}
    res = await client.post("/api/v1/checkout/validate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert any(i["code"] == "BRANCH_OFFLINE" for i in data["issues"])
