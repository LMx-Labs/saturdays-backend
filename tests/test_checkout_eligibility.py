"""Regression tests: checkout admission gates for is_paused, merchant status, inventory presence, and catalog lifecycle.

Targeted additions covering eligibility checks from the DineGuru integration:
  - ITEM_PAUSED:            inventory.is_paused=True must block checkout
  - MERCHANT_NOT_APPROVED:  merchant not in APPROVED status must block checkout
  - INSUFFICIENT_STOCK:     missing or soft-deleted inventory row must block checkout
  - ITEM_UNAVAILABLE:       item in soft-deleted category or inactive menu must block checkout

Each test builds its own isolated fixture to avoid state bleed.
Preserves pricing, idempotency and stock-check ordering.
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.cart.models import Cart, CartItem
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


async def _build_checkout_scenario(
    db: AsyncSession,
    *,
    tag: str,
    merchant_status: str = "APPROVED",
    inv_is_paused: bool = False,
    inv_is_in_stock: bool = True,
    inv_quantity: int = 10,
    has_inventory: bool = True,
    category_deleted: bool = False,
    inventory_deleted: bool = False,
    menu_active: bool = True,
) -> tuple[dict, str]:
    """Seed a minimal but complete checkout scenario. Returns (auth_headers, cart_id)."""
    user = User(
        email=f"elig_{tag}@sat.test",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    profile = CustomerProfile(user_id=user.id, full_name="Eligibility Tester")
    db.add(profile)
    await db.flush()

    merchant = Merchant(
        owner_user_id=user.id,
        business_name=f"Store {tag}",
        legal_entity_name=f"LLC {tag}",
        fssai_license_number="10000000000000",
        status=merchant_status,
    )
    db.add(merchant)
    await db.flush()

    brand = Brand(merchant_id=merchant.id, name=f"Brand {tag}")
    db.add(brand)
    await db.flush()

    branch = Branch(
        brand_id=brand.id,
        name=f"Branch {tag}",
        address_text="1 Test St",
        is_active=True,
    )
    db.add(branch)
    await db.flush()
    branch.closing_time = branch.opening_time  # always open

    kitchen = Kitchen(branch_id=branch.id, name="Main Kitchen", is_active=True)
    db.add(kitchen)
    await db.flush()

    menu = Menu(branch_id=branch.id, name="Menu", is_active=menu_active)
    db.add(menu)
    await db.flush()

    cat = MenuCategory(
        menu_id=menu.id,
        name="Items",
        display_order=0,
        deleted_at=datetime.now(UTC) if category_deleted else None,
    )
    db.add(cat)
    await db.flush()

    item = MenuItem(
        category_id=cat.id,
        name="Burger",
        base_price=150.0,
        is_available=True,
        is_veg=False,
    )
    db.add(item)
    await db.flush()

    if has_inventory:
        inv = InventoryItem(
            branch_id=branch.id,
            menu_item_id=item.id,
            quantity=inv_quantity,
            is_in_stock=inv_is_in_stock,
            is_paused=inv_is_paused,
            deleted_at=datetime.now(UTC) if inventory_deleted else None,
        )
        db.add(inv)
        await db.flush()

    cart = Cart(branch_id=branch.id, customer_profile_id=profile.id)
    db.add(cart)
    await db.flush()

    db.add(CartItem(cart_id=cart.id, menu_item_id=item.id, quantity=1))
    await db.commit()

    token = create_access_token(subject=str(user.id), role="Customer")
    return {"Authorization": f"Bearer {token}"}, str(cart.id)


@pytest.fixture
async def paused_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(db_session, tag="paused", inv_is_paused=True)


@pytest.fixture
async def paused_and_no_stock_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(
        db_session,
        tag="pausednostock",
        inv_is_paused=True,
        inv_is_in_stock=False,
        inv_quantity=0,
    )


@pytest.fixture
async def draft_merchant_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(
        db_session, tag="draft", merchant_status="DRAFT"
    )


@pytest.fixture
async def happy_path_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(db_session, tag="happy")


@pytest.fixture
async def no_inventory_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(db_session, tag="noinv", has_inventory=False)


@pytest.fixture
async def soft_deleted_category_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(
        db_session, tag="delcat", category_deleted=True
    )


@pytest.fixture
async def soft_deleted_inventory_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(
        db_session, tag="delinv", inventory_deleted=True
    )


@pytest.fixture
async def inactive_menu_scenario(db_session: AsyncSession):
    return await _build_checkout_scenario(
        db_session, tag="inactmenu", menu_active=False
    )


async def test_checkout_rejects_paused_inventory(
    client: AsyncClient, paused_scenario: tuple
) -> None:
    """ITEM_PAUSED code appears when inventory.is_paused is True."""
    headers, cart_id = paused_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "ITEM_PAUSED" in codes, f"Expected ITEM_PAUSED, got: {codes}"
    # is_paused gate fires before stock; INSUFFICIENT_STOCK must not appear
    assert "INSUFFICIENT_STOCK" not in codes


async def test_checkout_rejects_unapproved_merchant(
    client: AsyncClient, draft_merchant_scenario: tuple
) -> None:
    """MERCHANT_NOT_APPROVED code appears when merchant.status is not APPROVED."""
    headers, cart_id = draft_merchant_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert (
        "MERCHANT_NOT_APPROVED" in codes
    ), f"Expected MERCHANT_NOT_APPROVED, got: {codes}"


async def test_checkout_paused_takes_priority_over_stock(
    client: AsyncClient, paused_and_no_stock_scenario: tuple
) -> None:
    """When item is paused AND out-of-stock, only ITEM_PAUSED is reported."""
    headers, cart_id = paused_and_no_stock_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "ITEM_PAUSED" in codes
    assert (
        "INSUFFICIENT_STOCK" not in codes
    ), "is_paused check must short-circuit before stock check"


async def test_checkout_approved_merchant_active_item_passes(
    client: AsyncClient, happy_path_scenario: tuple
) -> None:
    """Happy path: APPROVED merchant, active branch, unpaused in-stock item -> is_valid=True."""
    headers, cart_id = happy_path_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    body = resp.json()
    assert (
        body["is_valid"] is True
    ), f"Expected valid checkout, got issues: {body.get('issues')}"
    assert body["subtotal"] == 150.0
    assert body["final_payable_amount"] == 150.0


async def test_checkout_rejects_item_with_no_inventory_row(
    client: AsyncClient, no_inventory_scenario: tuple
) -> None:
    """Carts containing items with absent inventory rows must quote as invalid with INSUFFICIENT_STOCK."""
    headers, cart_id = no_inventory_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "INSUFFICIENT_STOCK" in codes, f"Expected INSUFFICIENT_STOCK, got: {codes}"


async def test_checkout_rejects_soft_deleted_category(
    client: AsyncClient, soft_deleted_category_scenario: tuple
) -> None:
    """Carts containing items in soft-deleted categories must quote as invalid with ITEM_UNAVAILABLE."""
    headers, cart_id = soft_deleted_category_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "ITEM_UNAVAILABLE" in codes, f"Expected ITEM_UNAVAILABLE, got: {codes}"


async def test_checkout_rejects_soft_deleted_inventory_row(
    client: AsyncClient, soft_deleted_inventory_scenario: tuple
) -> None:
    """Carts containing items whose inventory row has been soft-deleted must quote as invalid."""
    headers, cart_id = soft_deleted_inventory_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "INSUFFICIENT_STOCK" in codes, f"Expected INSUFFICIENT_STOCK, got: {codes}"


async def test_checkout_rejects_inactive_menu(
    client: AsyncClient, inactive_menu_scenario: tuple
) -> None:
    """Carts containing items in inactive menus must quote as invalid with ITEM_UNAVAILABLE."""
    headers, cart_id = inactive_menu_scenario
    resp = await client.post(
        "/api/v1/checkout/validate",
        json={"cart_id": cart_id},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    codes = [i["code"] for i in body["issues"]]
    assert "ITEM_UNAVAILABLE" in codes, f"Expected ITEM_UNAVAILABLE, got: {codes}"
