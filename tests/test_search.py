import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import hash_password
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.fixture
async def setup_search_fixture(db_session: AsyncSession):
    user = User(
        email="searchowner@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="MerchantOwner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=user.id,
        business_name="Search Merchant",
        legal_entity_name="Search LLC",
        fssai_license_number="12345678909876",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(
        merchant_id=merchant.id,
        name="Taco Palace",
        description="Authentic Mexican Tacos and Burritos",
        cuisine_types=["Mexican", "Fast Food"],
    )
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id,
        name="Taco Palace Downtown",
        address_text="Downtown Street 42",
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    db_session.add(branch)
    await db_session.flush()

    menu = Menu(branch_id=branch.id, name="Main Menu", is_active=True)
    db_session.add(menu)
    await db_session.flush()

    category = MenuCategory(menu_id=menu.id, name="Mexican Tacos")
    db_session.add(category)
    await db_session.flush()

    item1 = MenuItem(
        category_id=category.id,
        name="Crispy Veg Taco",
        description="Delicious crispy taco with fresh salsa",
        base_price=99.00,
        is_veg=True,
        is_available=True,
    )
    item2 = MenuItem(
        category_id=category.id,
        name="Chicken Supreme Burrito",
        description="Loaded chicken burrito with spicy sauce",
        base_price=199.00,
        is_veg=False,
        is_available=True,
    )
    db_session.add_all([item1, item2])
    await db_session.commit()

    return {
        "branch": branch,
        "brand": brand,
        "item1": item1,
        "item2": item2,
    }


@pytest.mark.asyncio
async def test_search_restaurants_and_dishes(
    client: AsyncClient, setup_search_fixture: dict
):
    # Search for "Taco"
    res = await client.get("/api/v1/search?q=Taco")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["restaurants"]) >= 1 or len(data["dishes"]) >= 1

    # Filter by veg
    res_veg = await client.get("/api/v1/search?q=Taco&is_veg=true")
    assert res_veg.status_code == 200
    for dish in res_veg.json()["dishes"]:
        assert dish["is_veg"] is True


@pytest.mark.asyncio
async def test_search_location_and_sorting(
    client: AsyncClient, setup_search_fixture: dict
):
    # Location-aware search near Bangalore coordinates (12.9716, 77.5946)
    res_loc = await client.get(
        "/api/v1/search?latitude=12.9716&longitude=77.5946&radius_km=5.0"
    )
    assert res_loc.status_code == 200
    assert len(res_loc.json()["restaurants"]) >= 1
    assert res_loc.json()["restaurants"][0]["distance_km"] is not None

    # Price low to high sorting
    res_sort = await client.get("/api/v1/search?type=dish&sort_by=price_asc")
    assert res_sort.status_code == 200
    dishes = res_sort.json()["results"]
    if len(dishes) > 1:
        assert dishes[0]["price"] <= dishes[1]["price"]


@pytest.mark.asyncio
async def test_search_typeahead_suggestions(
    client: AsyncClient, setup_search_fixture: dict
):
    res = await client.get("/api/v1/search/suggestions?q=Tac")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "Tac"
    assert len(data["suggestions"]) >= 1

    # Empty query should fail
    res_err = await client.get("/api/v1/search/suggestions?q=  ")
    assert res_err.status_code == 400
    assert res_err.json()["error_code"] == "EMPTY_SEARCH_QUERY"
