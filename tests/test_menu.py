import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token, hash_password
from app.menu.models import Menu, MenuCategory
from app.merchant.models import Merchant


@pytest.fixture
async def setup_branch_and_manager(db_session: AsyncSession):
    """Helper fixture to create a merchant, brand, branch, menu, category, and manager token."""
    manager = User(
        email="manager@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="BranchManager",
        is_active=True,
    )
    db_session.add(manager)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=manager.id,
        business_name="Test Merchant",
        legal_entity_name="Test Merchant LLC",
        fssai_license_number="12345678901234",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(
        merchant_id=merchant.id, name="Test Brand", description="Test Description"
    )
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id,
        name="Test Branch",
        address_text="123 Campus Way",
    )
    db_session.add(branch)
    await db_session.flush()
    manager.branch_id = branch.id

    menu = Menu(branch_id=branch.id, name="Main Menu", is_active=True)
    db_session.add(menu)
    await db_session.flush()

    category = MenuCategory(menu_id=menu.id, name="Starters", display_order=1)
    db_session.add(category)
    await db_session.commit()

    token = create_access_token(subject=str(manager.id), role=manager.role)
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "manager": manager,
        "merchant": merchant,
        "brand": brand,
        "branch": branch,
        "menu": menu,
        "category": category,
        "headers": headers,
    }


@pytest.mark.asyncio
async def test_get_branch_menu_not_found(client: AsyncClient):
    random_branch_id = uuid.uuid4()
    response = await client.get(f"/api/v1/branches/{random_branch_id}/menu")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "MENU_NOT_FOUND"


@pytest.mark.asyncio
async def test_unassigned_manager_cannot_edit_other_branch_menu(
    client: AsyncClient, setup_branch_and_manager: dict, db_session: AsyncSession
):
    ctx = setup_branch_and_manager
    other = Branch(brand_id=ctx["brand"].id, name="Other", address_text="Elsewhere")
    db_session.add(other)
    await db_session.commit()
    denied = await client.post(
        f"/api/v1/branches/{other.id}/menus",
        json={"name": "Unauthorized"},
        headers=ctx["headers"],
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_create_and_get_branch_menu(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    category_id = ctx["category"].id
    headers = ctx["headers"]

    # Create menu item
    item_payload = {
        "category_id": str(category_id),
        "name": "Paneer Butter Masala",
        "description": "Rich tomato gravy with paneer cubes",
        "base_price": 240.50,
        "image_url": "http://example.com/paneer.jpg",
        "is_available": True,
        "is_veg": True,
    }
    response = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json=item_payload,
        headers=headers,
    )
    assert response.status_code == 201
    item_data = response.json()
    assert item_data["name"] == "Paneer Butter Masala"
    assert item_data["base_price"] == 240.50

    # Fetch full menu catalog
    menu_res = await client.get(f"/api/v1/branches/{branch_id}/menu")
    assert menu_res.status_code == 200
    menu_data = menu_res.json()
    assert menu_data["branch_id"] == str(branch_id)
    assert len(menu_data["categories"]) == 1
    assert len(menu_data["categories"][0]["items"]) == 1
    assert menu_data["categories"][0]["items"][0]["name"] == "Paneer Butter Masala"


@pytest.mark.asyncio
async def test_menu_item_negative_price_invariant(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    category_id = ctx["category"].id
    headers = ctx["headers"]

    item_payload = {
        "category_id": str(category_id),
        "name": "Invalid Price Item",
        "description": "Item with negative price",
        "base_price": -50.00,
        "is_available": True,
        "is_veg": True,
    }
    response = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json=item_payload,
        headers=headers,
    )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_menu_item_invalid_category_hierarchy(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    headers = ctx["headers"]
    fake_category_id = uuid.uuid4()

    item_payload = {
        "category_id": str(fake_category_id),
        "name": "Ghost Category Item",
        "base_price": 100.00,
    }
    response = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json=item_payload,
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_menu_item_unauthorized(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    category_id = ctx["category"].id

    item_payload = {
        "category_id": str(category_id),
        "name": "Unauthorized Item",
        "base_price": 100.00,
    }
    # No auth header
    response = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json=item_payload,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_category_success(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id
    headers = ctx["headers"]

    payload = {
        "name": "Beverages & Shakes",
        "display_order": 2,
    }
    response = await client.patch(
        f"/api/v1/menu/categories/{category_id}",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(category_id)
    assert data["name"] == "Beverages & Shakes"
    assert data["display_order"] == 2
    assert "menu_id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_update_category_partial(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id
    headers = ctx["headers"]

    # Update only name
    response = await client.patch(
        f"/api/v1/menu/categories/{category_id}",
        json={"name": "New Starters"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Starters"
    assert data["display_order"] == 1

    # Update only display_order
    response2 = await client.patch(
        f"/api/v1/menu/categories/{category_id}",
        json={"display_order": 5},
        headers=headers,
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["name"] == "New Starters"
    assert data2["display_order"] == 5


@pytest.mark.asyncio
async def test_update_category_not_found(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    headers = ctx["headers"]
    fake_category_id = uuid.uuid4()

    response = await client.patch(
        f"/api/v1/menu/categories/{fake_category_id}",
        json={"name": "Ghost Category"},
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_empty_category_success(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    headers = ctx["headers"]

    # Create a fresh empty category
    cat_res = await client.post(
        f"/api/v1/branches/{branch_id}/menu/categories",
        json={"name": "Empty Desserts", "display_order": 99},
        headers=headers,
    )
    assert cat_res.status_code == 201
    cat_id = cat_res.json()["id"]

    # Delete empty category
    del_res = await client.delete(
        f"/api/v1/menu/categories/{cat_id}",
        headers=headers,
    )
    assert del_res.status_code == 204

    # Verify category no longer retrievable
    patch_res = await client.patch(
        f"/api/v1/menu/categories/{cat_id}",
        json={"name": "Revived"},
        headers=headers,
    )
    assert patch_res.status_code == 404

    # Verify branch menu does not include the deleted category
    menu_res = await client.get(f"/api/v1/branches/{branch_id}/menu")
    assert menu_res.status_code == 200
    cat_ids = [c["id"] for c in menu_res.json()["categories"]]
    assert cat_id not in cat_ids


@pytest.mark.asyncio
async def test_delete_category_with_items_fails_without_fallback(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    category_id = ctx["category"].id
    headers = ctx["headers"]

    # Add an item to this category
    item_payload = {
        "category_id": str(category_id),
        "name": "Spring Rolls",
        "base_price": 120.00,
    }
    create_item_res = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json=item_payload,
        headers=headers,
    )
    assert create_item_res.status_code == 201

    # Attempt to delete without fallback
    del_res = await client.delete(
        f"/api/v1/menu/categories/{category_id}",
        headers=headers,
    )
    assert del_res.status_code == 400
    assert del_res.json()["error_code"] == "CATEGORY_NOT_EMPTY"


@pytest.mark.asyncio
async def test_delete_category_with_fallback_success(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    branch_id = ctx["branch"].id
    headers = ctx["headers"]

    # Create category A and category B
    cat_a_res = await client.post(
        f"/api/v1/branches/{branch_id}/menu/categories",
        json={"name": "Temporary Starters", "display_order": 10},
        headers=headers,
    )
    assert cat_a_res.status_code == 201
    cat_a_id = cat_a_res.json()["id"]

    cat_b_res = await client.post(
        f"/api/v1/branches/{branch_id}/menu/categories",
        json={"name": "Main Courses", "display_order": 20},
        headers=headers,
    )
    assert cat_b_res.status_code == 201
    cat_b_id = cat_b_res.json()["id"]

    # Add item to category A
    item_res = await client.post(
        f"/api/v1/branches/{branch_id}/menu/items",
        json={
            "category_id": cat_a_id,
            "name": "Crispy Corn",
            "base_price": 180.00,
        },
        headers=headers,
    )
    assert item_res.status_code == 201
    item_id = item_res.json()["id"]

    # Delete category A with fallback to category B
    del_res = await client.delete(
        f"/api/v1/menu/categories/{cat_a_id}?fallback_category_id={cat_b_id}",
        headers=headers,
    )
    assert del_res.status_code == 204

    # Verify item has been reassigned to category B
    item_check = await client.get(f"/api/v1/menu/items/{item_id}")
    assert item_check.status_code == 200
    assert item_check.json()["category_id"] == cat_b_id

    # Verify category A is no longer in branch menu, and category B contains the item
    menu_res = await client.get(f"/api/v1/branches/{branch_id}/menu")
    assert menu_res.status_code == 200
    menu_categories = {c["id"]: c for c in menu_res.json()["categories"]}
    assert cat_a_id not in menu_categories
    assert cat_b_id in menu_categories
    cat_b_item_ids = [it["id"] for it in menu_categories[cat_b_id]["items"]]
    assert item_id in cat_b_item_ids


@pytest.mark.asyncio
async def test_delete_category_invalid_fallback_same_category(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id
    headers = ctx["headers"]

    del_res = await client.delete(
        f"/api/v1/menu/categories/{category_id}?fallback_category_id={category_id}",
        headers=headers,
    )
    assert del_res.status_code == 400
    assert del_res.json()["error_code"] == "INVALID_FALLBACK_CATEGORY"


@pytest.mark.asyncio
async def test_delete_category_fallback_not_found(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id
    headers = ctx["headers"]
    fake_fallback_id = uuid.uuid4()

    del_res = await client.delete(
        f"/api/v1/menu/categories/{category_id}?fallback_category_id={fake_fallback_id}",
        headers=headers,
    )
    assert del_res.status_code == 404
    assert del_res.json()["error_code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_category_fallback_different_menu(
    client: AsyncClient, setup_branch_and_manager: dict, db_session: AsyncSession
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id
    brand = ctx["brand"]
    headers = ctx["headers"]

    # Create a second branch with its own menu and category
    branch2 = Branch(
        brand_id=brand.id,
        name="Branch 2",
        address_text="456 Other Way",
    )
    db_session.add(branch2)
    await db_session.flush()

    menu2 = Menu(branch_id=branch2.id, name="Branch 2 Menu", is_active=True)
    db_session.add(menu2)
    await db_session.flush()

    cat_other = MenuCategory(menu_id=menu2.id, name="Other Branch Cat", display_order=1)
    db_session.add(cat_other)
    await db_session.commit()

    del_res = await client.delete(
        f"/api/v1/menu/categories/{category_id}?fallback_category_id={cat_other.id}",
        headers=headers,
    )
    assert del_res.status_code == 403
    assert del_res.json()["error_code"] == "BRANCH_ACCESS_FORBIDDEN"


@pytest.mark.asyncio
async def test_category_endpoints_rbac(
    client: AsyncClient, setup_branch_and_manager: dict, db_session: AsyncSession
):
    ctx = setup_branch_and_manager
    category_id = ctx["category"].id

    # Unauthenticated PATCH
    patch_res = await client.patch(
        f"/api/v1/menu/categories/{category_id}",
        json={"name": "Hacked"},
    )
    assert patch_res.status_code == 401

    # Unauthenticated DELETE
    del_res = await client.delete(
        f"/api/v1/menu/categories/{category_id}",
    )
    assert del_res.status_code == 401

    # Customer role (forbidden)
    customer = User(email="menu_customer@example.com", role="Customer", is_active=True)
    db_session.add(customer)
    await db_session.commit()
    cust_token = create_access_token(subject=str(customer.id), role="Customer")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    patch_cust = await client.patch(
        f"/api/v1/menu/categories/{category_id}",
        json={"name": "Customer Rename"},
        headers=cust_headers,
    )
    assert patch_cust.status_code == 403

    del_cust = await client.delete(
        f"/api/v1/menu/categories/{category_id}",
        headers=cust_headers,
    )
    assert del_cust.status_code == 403
