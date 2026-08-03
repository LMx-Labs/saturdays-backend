import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token, hash_password
from app.menu.models import Menu, MenuCategory


@pytest.fixture
async def setup_branch_and_manager(db_session: AsyncSession):
    """Helper fixture to create a brand, branch, menu, category, and manager token."""
    manager = User(
        email="manager@saturdays.com",
        password_hash=hash_password("Password123!"),
        full_name="Branch Manager",
        role="BranchManager",
        is_active=True,
    )
    db_session.add(manager)
    await db_session.flush()

    brand = Brand(name="Test Brand", description="Test Description")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id,
        name="Test Branch",
        address_text="123 Campus Way",
    )
    db_session.add(branch)
    await db_session.flush()

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
async def test_create_and_get_branch_menu(client: AsyncClient, setup_branch_and_manager: dict):
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
async def test_menu_item_unauthorized(client: AsyncClient, setup_branch_and_manager: dict):
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
