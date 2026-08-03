import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.exceptions import DomainInvariantError
from app.core.security import create_access_token, hash_password
from app.inventory.models import InventoryItem
from app.inventory.repository import InventoryRepository
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.fixture
async def setup_inventory_fixture(db_session: AsyncSession):
    """Helper fixture for inventory tests."""
    kitchen_staff = User(
        email="kitchen@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="KitchenStaff",
        is_active=True,
    )
    db_session.add(kitchen_staff)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=kitchen_staff.id,
        business_name="Kitchen Merchant",
        legal_entity_name="Kitchen Merchant LLC",
        fssai_license_number="98765432101234",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Kitchen Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id, name="Campus Kitchen Branch", address_text="Block A"
    )
    db_session.add(branch)
    await db_session.flush()

    menu = Menu(branch_id=branch.id, name="Main Menu")
    db_session.add(menu)
    await db_session.flush()

    category = MenuCategory(menu_id=menu.id, name="Main Course")
    db_session.add(category)
    await db_session.flush()

    menu_item = MenuItem(
        category_id=category.id, name="Chicken Roll", base_price=120.00
    )
    db_session.add(menu_item)
    await db_session.flush()

    inventory_item = InventoryItem(
        branch_id=branch.id,
        menu_item_id=menu_item.id,
        quantity=10,
        is_in_stock=True,
    )
    db_session.add(inventory_item)
    await db_session.commit()

    token = create_access_token(subject=str(kitchen_staff.id), role=kitchen_staff.role)
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "kitchen_staff": kitchen_staff,
        "branch": branch,
        "menu_item": menu_item,
        "inventory_item": inventory_item,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_get_branch_inventory(client: AsyncClient, setup_inventory_fixture: dict):
    ctx = setup_inventory_fixture
    branch_id = ctx["branch"].id
    headers = ctx["headers"]

    response = await client.get(
        f"/api/v1/branches/{branch_id}/inventory",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["quantity"] == 10
    assert data[0]["is_in_stock"] is True


@pytest.mark.asyncio
async def test_update_stock_quantity(
    client: AsyncClient, setup_inventory_fixture: dict
):
    ctx = setup_inventory_fixture
    inv_id = ctx["inventory_item"].id
    headers = ctx["headers"]

    payload = {
        "quantity": 50,
        "reason": "MERCHANT_RESTOCK",
    }
    response = await client.patch(
        f"/api/v1/inventory/{inv_id}/stock",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 50
    assert data["is_in_stock"] is True


@pytest.mark.asyncio
async def test_negative_stock_quantity_invariant(
    client: AsyncClient, setup_inventory_fixture: dict
):
    ctx = setup_inventory_fixture
    inv_id = ctx["inventory_item"].id
    headers = ctx["headers"]

    payload = {
        "quantity": -5,
        "reason": "INVALID_ADJUSTMENT",
    }
    response = await client.patch(
        f"/api/v1/inventory/{inv_id}/stock",
        json=payload,
        headers=headers,
    )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_pessimistic_lock_stock_reservation(
    db_session: AsyncSession, setup_inventory_fixture: dict
):
    ctx = setup_inventory_fixture
    branch_id = ctx["branch"].id
    menu_item_id = ctx["menu_item"].id

    repo = InventoryRepository(session=db_session)

    # Reserve 6 units out of 10
    item = await repo.reserve_stock(
        branch_id=branch_id, menu_item_id=menu_item_id, quantity=6
    )
    assert item.quantity == 4
    assert item.is_in_stock is True

    # Reserve remaining 4 units
    item_depleted = await repo.reserve_stock(
        branch_id=branch_id, menu_item_id=menu_item_id, quantity=4
    )
    assert item_depleted.quantity == 0
    assert item_depleted.is_in_stock is False

    # Attempt to reserve 1 more unit (insufficient stock invariant failure)
    with pytest.raises(DomainInvariantError) as exc_info:
        await repo.reserve_stock(
            branch_id=branch_id, menu_item_id=menu_item_id, quantity=1
        )
    assert exc_info.value.error_code == "INSUFFICIENT_STOCK"


@pytest.mark.asyncio
async def test_inventory_unauthorized(
    client: AsyncClient, setup_inventory_fixture: dict
):
    ctx = setup_inventory_fixture
    inv_id = ctx["inventory_item"].id

    payload = {"quantity": 20}
    response = await client.patch(
        f"/api/v1/inventory/{inv_id}/stock",
        json=payload,
    )
    assert response.status_code == 401
