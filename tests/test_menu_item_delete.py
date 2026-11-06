"""Removing a dish from the menu."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.menu.models import MenuItem
from tests.conftest import seed_user_login


async def _add_item(
    client: AsyncClient, ctx: dict, name: str = "Chicken Biryani"
) -> str:
    res = await client.post(
        f"/api/v1/branches/{ctx['branch'].id}/menu/items",
        json={
            "category_id": str(ctx["category"].id),
            "name": name,
            "description": "Fresh",
            "base_price": 150,
            "is_available": True,
            "is_veg": False,
        },
        headers=ctx["headers"],
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def test_delete_removes_the_dish_from_the_menu(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    keep = await _add_item(client, ctx, "Veg Biryani")
    gone = await _add_item(client, ctx, "Chicken Biryani")

    res = await client.delete(f"/api/v1/menu/items/{gone}", headers=ctx["headers"])
    assert res.status_code == 204

    # (The menu listing itself is checked on a real database, with one session
    # per request, in test_menu_delete_postgres.py.)
    assert (await client.get(f"/api/v1/menu/items/{gone}")).status_code == 404
    assert (await client.get(f"/api/v1/menu/items/{keep}")).status_code == 200


async def test_delete_is_soft_so_past_orders_keep_their_record(
    client: AsyncClient, db_session: AsyncSession, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    item_id = await _add_item(client, ctx)
    await client.delete(f"/api/v1/menu/items/{item_id}", headers=ctx["headers"])

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(MenuItem).where(MenuItem.id == uuid.UUID(item_id))
        )
    ).scalar_one()
    assert row.deleted_at is not None
    assert row.is_available is False


async def test_deleting_twice_or_unknown_is_404(
    client: AsyncClient, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    item_id = await _add_item(client, ctx)
    assert (
        await client.delete(f"/api/v1/menu/items/{item_id}", headers=ctx["headers"])
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/menu/items/{item_id}", headers=ctx["headers"])
    ).status_code == 404
    unknown = "01a19ba4-21aa-79de-98c9-732e4392191d"
    assert (
        await client.delete(f"/api/v1/menu/items/{unknown}", headers=ctx["headers"])
    ).status_code == 404


async def test_deleted_dish_leaves_customers_carts(
    client: AsyncClient, db_session: AsyncSession, setup_branch_and_manager: dict
):
    ctx = setup_branch_and_manager
    item_id = await _add_item(client, ctx)
    login = await seed_user_login(client, db_session, "hungry@saturdays.com")
    cart_headers = {"Authorization": f"Bearer {login['access_token']}"}
    added = await client.post(
        "/api/v1/cart/items",
        headers=cart_headers,
        json={
            "branch_id": str(ctx["branch"].id),
            "menu_item_id": item_id,
            "quantity": 2,
        },
    )
    assert added.status_code == 200, added.text

    await client.delete(f"/api/v1/menu/items/{item_id}", headers=ctx["headers"])

    cart = (await client.get("/api/v1/cart", headers=cart_headers)).json()
    assert cart["items"] == []


@pytest.mark.parametrize("role", ["Customer", "KitchenStaff"])
async def test_only_menu_staff_can_delete(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_branch_and_manager: dict,
    role: str,
):
    ctx = setup_branch_and_manager
    item_id = await _add_item(client, ctx)
    login = await seed_user_login(
        client, db_session, f"{role.lower()}.del@saturdays.com", role=role
    )
    res = await client.delete(
        f"/api/v1/menu/items/{item_id}",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert res.status_code == 403
    assert (await client.get(f"/api/v1/menu/items/{item_id}")).status_code == 200


async def test_delete_requires_login(
    client: AsyncClient, setup_branch_and_manager: dict
):
    item_id = await _add_item(client, setup_branch_and_manager)
    assert (await client.delete(f"/api/v1/menu/items/{item_id}")).status_code == 401
