"""Cart behaviour that broke in production: missing profiles and duplicates."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cart.models import Cart, CartItem
from app.customer.repository import CustomerRepository
from tests.conftest import seed_user_login


def _auth(login: dict) -> dict:
    return {"Authorization": f"Bearer {login['access_token']}"}


async def _add(client: AsyncClient, headers: dict, fixture: dict, qty: int = 1):
    return await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "branch_id": fixture["branch_a_id"],
            "menu_item_id": fixture["item_available_id"],
            "quantity": qty,
        },
    )


async def test_new_customer_can_add_to_cart_without_visiting_profile(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_cart_fixture: dict,
):
    """Registration doesn't create a profile; the first add used to 404."""
    login = await seed_user_login(client, db_session, "fresh@saturdays.com")
    resp = await _add(client, _auth(login), setup_cart_fixture, qty=2)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_items"] == 2

    me = await client.get("/api/v1/customers/me", headers=_auth(login))
    assert me.status_code == 200


@pytest.mark.parametrize("role", ["MerchantOwner", "PlatformAdmin"])
async def test_staff_accounts_still_get_profile_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_cart_fixture: dict,
    role: str,
):
    login = await seed_user_login(
        client, db_session, f"{role.lower()}@saturdays.com", role=role
    )
    resp = await _add(client, _auth(login), setup_cart_fixture)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "CUSTOMER_NOT_FOUND"


async def test_get_or_create_profile_is_idempotent(
    db_session: AsyncSession, setup_cart_fixture: dict
):
    user_id = setup_cart_fixture["cust_user"].id
    repo = CustomerRepository(db_session)
    first = await repo.get_or_create_by_user_id(user_id)
    second = await repo.get_or_create_by_user_id(user_id)
    assert first.id == second.id


async def test_database_rejects_duplicate_carts_and_lines(
    db_session: AsyncSession, setup_cart_fixture: dict
):
    user_id = setup_cart_fixture["cust_user"].id
    profile = await CustomerRepository(db_session).get_or_create_by_user_id(user_id)
    # Plain values: ORM objects are expired by the rollbacks below.
    profile_id = profile.id
    branch_a = uuid.UUID(setup_cart_fixture["branch_a_id"])
    branch_b = uuid.UUID(setup_cart_fixture["branch_b_id"])
    item_id = uuid.UUID(setup_cart_fixture["item_available_id"])

    cart = Cart(customer_profile_id=profile_id, branch_id=branch_a)
    db_session.add(cart)
    await db_session.flush()
    cart_id = cart.id
    db_session.add(CartItem(cart_id=cart_id, menu_item_id=item_id, quantity=1))
    await db_session.commit()

    db_session.add(CartItem(cart_id=cart_id, menu_item_id=item_id, quantity=1))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    db_session.add(Cart(customer_profile_id=profile_id, branch_id=branch_b))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_repeated_adds_accumulate_in_one_line(
    client: AsyncClient,
    db_session: AsyncSession,
    setup_cart_fixture: dict,
):
    login = await seed_user_login(client, db_session, "tapper@saturdays.com")
    headers = _auth(login)
    for _ in range(4):
        assert (await _add(client, headers, setup_cart_fixture)).status_code == 200
    cart = (await client.get("/api/v1/cart", headers=headers)).json()
    assert [(i["menu_item_id"], i["quantity"]) for i in cart["items"]] == [
        (setup_cart_fixture["item_available_id"], 4)
    ]
