import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token
from app.inventory.models import InventoryItem
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.mark.asyncio
async def test_foreign_owner_and_unassigned_staff_cannot_change_menu_or_stock(
    client: AsyncClient, db_session: AsyncSession
):
    owner_a = User(email="owner-a@example.com", role="MerchantOwner", is_active=True)
    owner_b = User(email="owner-b@example.com", role="MerchantOwner", is_active=True)
    staff = User(email="unassigned@example.com", role="KitchenStaff", is_active=True)
    db_session.add_all([owner_a, owner_b, staff])
    await db_session.flush()
    merchant = Merchant(
        owner_user_id=owner_a.id,
        business_name="A",
        legal_entity_name="A",
        fssai_license_number="12345678901234",
        status="APPROVED",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="A")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="A", address_text="A")
    db_session.add(branch)
    await db_session.flush()
    menu = Menu(branch_id=branch.id, name="Main")
    db_session.add(menu)
    await db_session.flush()
    category = MenuCategory(menu_id=menu.id, name="Mains")
    db_session.add(category)
    await db_session.flush()
    item = MenuItem(category_id=category.id, name="Soup", base_price=20)
    db_session.add(item)
    await db_session.flush()
    stock = InventoryItem(
        branch_id=branch.id, menu_item_id=item.id, quantity=5, is_in_stock=True
    )
    db_session.add(stock)
    await db_session.commit()

    def headers(user: User) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role)}"
        }

    for actor in (owner_b, staff):
        changed = await client.patch(
            f"/api/v1/menu/items/{item.id}",
            json={"base_price": 1},
            headers=headers(actor),
        )
        assert changed.status_code == 403
        stock_changed = await client.patch(
            f"/api/v1/inventory/{stock.id}/stock",
            json={"quantity": 100, "expected_quantity": 5},
            headers=headers(actor),
        )
        assert stock_changed.status_code == 403
    await db_session.refresh(item)
    await db_session.refresh(stock)
    assert float(item.base_price) == 20
    assert stock.quantity == 5
    own = await client.patch(
        f"/api/v1/menu/items/{item.id}",
        json={"base_price": 25},
        headers=headers(owner_a),
    )
    assert own.status_code == 200


@pytest.mark.asyncio
async def test_merchant_private_response_rejected_for_customer_and_other_owner(
    client: AsyncClient, db_session: AsyncSession
):
    owner = User(
        email="private-owner@example.com", role="MerchantOwner", is_active=True
    )
    foreign = User(
        email="private-foreign@example.com", role="MerchantOwner", is_active=True
    )
    customer = User(
        email="private-customer@example.com", role="Customer", is_active=True
    )
    db_session.add_all([owner, foreign, customer])
    await db_session.flush()
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Private",
        legal_entity_name="Private",
        fssai_license_number="12345678901234",
        bank_account_number="synthetic-account",
        bank_ifsc_code="TEST0000001",
    )
    db_session.add(merchant)
    await db_session.commit()
    for actor in (foreign, customer):
        token = create_access_token(subject=str(actor.id), role=actor.role)
        response = await client.get(
            f"/api/v1/merchants/{merchant.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "synthetic-account" not in response.text
