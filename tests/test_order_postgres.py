"""Real PostgreSQL admission checks against an isolated migrated test database.

Set TEST_POSTGRES_URL to a database whose name starts with dineguru_repair_.
Never point this module at a live or shared application database.
"""

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.database import get_db_session
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.main import app
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.order.models import Order, OrderReservation

TEST_URL = os.getenv("TEST_POSTGRES_URL")
if not TEST_URL:
    pytest.skip("TEST_POSTGRES_URL is not configured", allow_module_level=True)
if not make_url(TEST_URL).database.startswith("dineguru_repair_"):
    raise RuntimeError("PostgreSQL tests require an isolated dineguru_repair_ database")


@pytest.fixture
async def pg_context():
    engine = create_async_engine(TEST_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def get_test_session():
        async with sessions() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = get_test_session
    async with sessions() as session:
        owner = User(
            email=f"owner-{uuid.uuid4()}@example.com",
            role="MerchantOwner",
            is_active=True,
        )
        customers = [
            User(
                email=f"customer-{uuid.uuid4()}@example.com",
                role="Customer",
                is_active=True,
            )
            for _ in range(2)
        ]
        session.add_all([owner, *customers])
        await session.flush()
        profiles = [
            CustomerProfile(user_id=user.id, full_name="Race Customer")
            for user in customers
        ]
        session.add_all(profiles)
        merchant = Merchant(
            owner_user_id=owner.id,
            business_name="Race Merchant",
            legal_entity_name="Race Merchant",
            fssai_license_number="12345678901234",
            status="APPROVED",
        )
        session.add(merchant)
        await session.flush()
        brand = Brand(merchant_id=merchant.id, name="Race Brand")
        session.add(brand)
        await session.flush()
        branch = Branch(
            brand_id=brand.id,
            name="Race Branch",
            address_text="Test Lane",
        )
        session.add(branch)
        await session.flush()
        branch.closing_time = branch.opening_time
        session.add(Kitchen(branch_id=branch.id, name="Main Kitchen", is_active=True))
        menu = Menu(branch_id=branch.id, name="Main", is_active=True)
        session.add(menu)
        await session.flush()
        category = MenuCategory(menu_id=menu.id, name="Meals")
        session.add(category)
        await session.flush()
        items = [
            MenuItem(category_id=category.id, name=f"Meal {n}", base_price=20)
            for n in range(2)
        ]
        session.add_all(items)
        await session.flush()
        inventory = [
            InventoryItem(
                branch_id=branch.id, menu_item_id=item.id, quantity=1, is_in_stock=True
            )
            for item in items
        ]
        # Deliberately invert inventory ID order relative to menu ID order.
        inventory_ids = sorted((uuid.uuid4(), uuid.uuid4()))
        menu_order = sorted(range(2), key=lambda index: str(items[index].id))
        inventory[menu_order[0]].id = inventory_ids[1]
        inventory[menu_order[1]].id = inventory_ids[0]
        session.add_all(inventory)
        await session.commit()
        data = {
            "sessions": sessions,
            "branch_id": branch.id,
            "item_ids": [item.id for item in items],
            "inventory_ids": [row.id for row in inventory],
            "customer_ids": [profile.id for profile in profiles],
            "owner_headers": {
                "Authorization": f"Bearer {create_access_token(subject=str(owner.id), role='MerchantOwner')}"
            },
            "headers": [
                {
                    "Authorization": f"Bearer {create_access_token(subject=str(user.id), role='Customer')}",
                    "Idempotency-Key": f"race-{uuid.uuid4()}",
                }
                for user in customers
            ],
        }
    try:
        yield data
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_last_unit_race_reserves_once(pg_context):
    ctx = pg_context
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [{"menu_item_id": str(ctx["item_ids"][0]), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = await asyncio.gather(
            *[
                client.post("/api/v1/orders", json=payload, headers=headers)
                for headers in ctx["headers"]
            ]
        )
    assert sorted(response.status_code for response in responses) == [201, 400]
    assert (
        next(response for response in responses if response.status_code == 400).json()[
            "error_code"
        ]
        == "INSUFFICIENT_STOCK"
    )
    async with ctx["sessions"]() as session:
        stock = await session.get(InventoryItem, ctx["inventory_ids"][0])
        assert stock.quantity == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OrderReservation)
                .where(OrderReservation.inventory_item_id == stock.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_later_stock_failure_rolls_back_earlier_reservation(pg_context):
    ctx = pg_context
    ordered = sorted(
        zip(ctx["item_ids"], ctx["inventory_ids"]), key=lambda pair: str(pair[0])
    )
    async with ctx["sessions"]() as session:
        later = await session.get(InventoryItem, ordered[1][1])
        later.quantity = 0
        later.is_in_stock = False
        await session.commit()
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [
            {"menu_item_id": str(item_id), "quantity": 1}
            for item_id, _ in reversed(ordered)
        ],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INSUFFICIENT_STOCK"
    async with ctx["sessions"]() as session:
        earlier = await session.get(InventoryItem, ordered[0][1])
        assert earlier.quantity == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.customer_profile_id == ctx["customer_ids"][0])
            )
            == 0
        )


@pytest.mark.asyncio
async def test_later_invalid_item_never_reserves_earlier_stock(pg_context):
    ctx = pg_context
    first_item, first_inventory = min(
        zip(ctx["item_ids"], ctx["inventory_ids"]), key=lambda pair: str(pair[0])
    )
    invalid_item = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [
            {"menu_item_id": str(first_item), "quantity": 1},
            {"menu_item_id": str(invalid_item), "quantity": 1},
        ],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
    assert response.status_code == 404
    assert response.json()["error_code"] == "MENU_ITEM_NOT_FOUND"
    async with ctx["sessions"]() as session:
        stock = await session.get(InventoryItem, first_inventory)
        assert stock.quantity == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OrderReservation)
                .where(OrderReservation.inventory_item_id == first_inventory)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_reversed_multi_item_race_and_cancellation_once(pg_context):
    ctx = pg_context
    first_items = [
        {"menu_item_id": str(item_id), "quantity": 1} for item_id in ctx["item_ids"]
    ]
    payloads = [
        {
            "branch_id": str(ctx["branch_id"]),
            "items": items,
            "delivery_address_snapshot": {"address_line": "Test"},
        }
        for items in (first_items, list(reversed(first_items)))
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = await asyncio.wait_for(
            asyncio.gather(
                *[
                    client.post("/api/v1/orders", json=payload, headers=headers)
                    for payload, headers in zip(payloads, ctx["headers"])
                ]
            ),
            timeout=10,
        )
        assert sorted(response.status_code for response in responses) == [201, 400]
        created = next(
            response for response in responses if response.status_code == 201
        )
        winner = responses.index(created)
        order_id = created.json()["id"]
        cancels = await asyncio.wait_for(
            asyncio.gather(
                *[
                    client.post(
                        f"/api/v1/orders/{order_id}/cancel",
                        headers=ctx["headers"][winner],
                    )
                    for _ in range(2)
                ]
            ),
            timeout=10,
        )
        assert sorted(response.status_code for response in cancels) == [200, 400], [
            response.json() for response in cancels
        ]
    async with ctx["sessions"]() as session:
        for inventory_id in ctx["inventory_ids"]:
            row = await session.get(InventoryItem, inventory_id)
            assert row.quantity == 1
        holds = (
            await session.scalars(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(order_id)
                )
            )
        ).all()
        assert len(holds) == 2
        assert all(hold.released_at is not None for hold in holds)


@pytest.mark.asyncio
async def test_concurrent_identical_retries_return_one_order(pg_context):
    ctx = pg_context
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [{"menu_item_id": str(ctx["item_ids"][0]), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = await asyncio.wait_for(
            asyncio.gather(
                *[
                    client.post(
                        "/api/v1/orders", json=payload, headers=ctx["headers"][0]
                    )
                    for _ in range(2)
                ]
            ),
            timeout=10,
        )
    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    async with ctx["sessions"]() as session:
        row = await session.get(InventoryItem, ctx["inventory_ids"][0])
        assert row.quantity == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.customer_profile_id == ctx["customer_ids"][0])
            )
            == 1
        )


@pytest.mark.asyncio
async def test_cancellation_and_owner_stock_edit_do_not_lose_updates(pg_context):
    ctx = pg_context
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [{"menu_item_id": str(ctx["item_ids"][0]), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]
        cancelled, edited = await asyncio.wait_for(
            asyncio.gather(
                client.post(
                    f"/api/v1/orders/{order_id}/cancel", headers=ctx["headers"][0]
                ),
                client.patch(
                    f"/api/v1/inventory/{ctx['inventory_ids'][0]}/stock",
                    json={"quantity": 5, "expected_quantity": 0, "is_in_stock": True},
                    headers=ctx["owner_headers"],
                ),
            ),
            timeout=10,
        )
    assert cancelled.status_code == 200, cancelled.text
    assert edited.status_code in {200, 409}, edited.text
    async with ctx["sessions"]() as session:
        stock = await session.get(InventoryItem, ctx["inventory_ids"][0])
        assert stock.quantity == (6 if edited.status_code == 200 else 1)


@pytest.mark.asyncio
async def test_distinct_line_prices_and_quantities_match_saved_subtotal(pg_context):
    ctx = pg_context
    async with ctx["sessions"]() as session:
        first = await session.get(MenuItem, ctx["item_ids"][0])
        second = await session.get(MenuItem, ctx["item_ids"][1])
        first.base_price = 20
        second.base_price = 80
        stock = await session.get(InventoryItem, ctx["inventory_ids"][0])
        stock.quantity = 2
        await session.commit()
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [
            {"menu_item_id": str(ctx["item_ids"][1]), "quantity": 1},
            {"menu_item_id": str(ctx["item_ids"][0]), "quantity": 2},
        ],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
    assert response.status_code == 201, response.text
    saved = response.json()
    lines = {line["menu_item_id"]: line for line in saved["items"]}
    assert lines[str(ctx["item_ids"][0])]["unit_price_snapshot"] == 20
    assert lines[str(ctx["item_ids"][1])]["unit_price_snapshot"] == 80
    assert (
        sum(line["unit_price_snapshot"] * line["quantity"] for line in saved["items"])
        == 120
    )
    assert saved["total_amount"] == 120
    assert saved["price_breakdown_snapshot"]["subtotal"] == "120.00"


@pytest.mark.asyncio
async def test_manual_pause_survives_cancellation_and_replenishment(pg_context):
    ctx = pg_context
    stock_id = ctx["inventory_ids"][0]
    async with ctx["sessions"]() as session:
        stock = await session.get(InventoryItem, stock_id)
        stock.quantity = 2
        await session.commit()
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [{"menu_item_id": str(ctx["item_ids"][0]), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
        assert created.status_code == 201, created.text
        paused = await client.patch(
            f"/api/v1/inventory/{stock_id}/stock",
            json={"quantity": 1, "expected_quantity": 1, "is_in_stock": False},
            headers=ctx["owner_headers"],
        )
        assert paused.status_code == 200, paused.text
        cancelled = await client.post(
            f"/api/v1/orders/{created.json()['id']}/cancel", headers=ctx["headers"][0]
        )
        assert cancelled.status_code == 200, cancelled.text
        stock = await client.patch(
            f"/api/v1/inventory/{stock_id}/stock",
            json={"quantity": 0, "expected_quantity": 2, "is_in_stock": False},
            headers=ctx["owner_headers"],
        )
        assert stock.status_code == 200, stock.text
        replenished = await client.patch(
            f"/api/v1/inventory/{stock_id}/stock",
            json={"quantity": 2, "expected_quantity": 0},
            headers=ctx["owner_headers"],
        )
        assert replenished.status_code == 200, replenished.text
        assert replenished.json()["is_paused"] is True
        assert replenished.json()["is_in_stock"] is False
        resumed = await client.patch(
            f"/api/v1/inventory/{stock_id}/stock",
            json={"quantity": 2, "expected_quantity": 2, "is_in_stock": True},
            headers=ctx["owner_headers"],
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["is_paused"] is False
        assert resumed.json()["is_in_stock"] is True
        exhausted = await client.post(
            "/api/v1/orders",
            json={
                **payload,
                "items": [{"menu_item_id": str(ctx["item_ids"][0]), "quantity": 2}],
            },
            headers=ctx["headers"][1],
        )
        assert exhausted.status_code == 201, exhausted.text
        released = await client.post(
            f"/api/v1/orders/{exhausted.json()['id']}/cancel", headers=ctx["headers"][1]
        )
        assert released.status_code == 200, released.text
    async with ctx["sessions"]() as session:
        row = await session.get(InventoryItem, stock_id)
        assert row.quantity == 2
        assert row.is_paused is False and row.is_in_stock is True


@pytest.mark.asyncio
async def test_inverted_inventory_ids_checkout_racing_cancellation(pg_context):
    ctx = pg_context
    paired = sorted(
        zip(ctx["item_ids"], ctx["inventory_ids"]), key=lambda pair: str(pair[0])
    )
    assert str(paired[0][1]) > str(paired[1][1])
    async with ctx["sessions"]() as session:
        for stock_id in ctx["inventory_ids"]:
            stock = await session.get(InventoryItem, stock_id)
            stock.quantity = 2
        await session.commit()
    payload = {
        "branch_id": str(ctx["branch_id"]),
        "items": [
            {"menu_item_id": str(item_id), "quantity": 1} for item_id in ctx["item_ids"]
        ],
        "delivery_address_snapshot": {"address_line": "Test"},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/api/v1/orders", json=payload, headers=ctx["headers"][0]
        )
        assert first.status_code == 201, first.text
        second, cancelled = await asyncio.wait_for(
            asyncio.gather(
                client.post("/api/v1/orders", json=payload, headers=ctx["headers"][1]),
                client.post(
                    f"/api/v1/orders/{first.json()['id']}/cancel",
                    headers=ctx["headers"][0],
                ),
            ),
            timeout=10,
        )
        assert second.status_code == 201, second.text
        assert cancelled.status_code == 200, cancelled.text
    async with ctx["sessions"]() as session:
        for stock_id in ctx["inventory_ids"]:
            row = await session.get(InventoryItem, stock_id)
            assert row.quantity == 1
        holds = (
            await session.scalars(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(first.json()["id"])
                )
            )
        ).all()
        assert len(holds) == 2 and all(hold.released_at for hold in holds)


@pytest.mark.asyncio
async def test_authenticated_admin_owner_customer_order_journey(pg_context):
    ctx = pg_context
    async with ctx["sessions"]() as session:
        admin = User(
            email=f"journey-admin-{uuid.uuid4()}@example.com",
            password_hash=hash_password("AdminPassword123!"),
            role="PlatformAdmin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        admin_id = admin.id
    admin_headers = {
        "Authorization": f"Bearer {create_access_token(subject=str(admin_id), role='PlatformAdmin')}"
    }
    owner_email = f"journey-owner-{uuid.uuid4()}@example.com"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        owner = await client.post(
            "/api/v1/admin/staff-accounts",
            json={
                "email": owner_email,
                "password": "OwnerPassword123!",
                "role": "MerchantOwner",
            },
            headers=admin_headers,
        )
        assert owner.status_code == 201, owner.text
        owner_id = owner.json()["user_id"]
        merchant = await client.post(
            f"/api/v1/admin/merchant-for-owner/{owner_id}",
            json={
                "business_name": "Journey Restaurant",
                "legal_entity_name": "Journey Restaurant Ltd",
                "fssai_license_number": "12345678901234",
            },
            headers=admin_headers,
        )
        assert merchant.status_code == 201, merchant.text
        merchant_id = merchant.json()["id"]
        approved = await client.post(
            f"/api/v1/admin/merchants/{merchant_id}/approval",
            json={"action": "APPROVE", "reason": "Verified for isolated acceptance"},
            headers=admin_headers,
        )
        assert approved.status_code == 200, approved.text
        brand = await client.post(
            "/api/v1/brands",
            json={"merchant_id": merchant_id, "name": "Journey Brand"},
            headers=admin_headers,
        )
        assert brand.status_code == 201, brand.text
        branch = await client.post(
            "/api/v1/branches",
            json={
                "brand_id": brand.json()["id"],
                "name": "Journey Branch",
                "address_text": "Isolated Test Lane",
                "opening_time": "00:00:00",
                "closing_time": "00:00:00",
            },
            headers=admin_headers,
        )
        assert branch.status_code == 201, branch.text
        branch_id = branch.json()["id"]
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": owner_email, "password": "OwnerPassword123!"},
        )
        assert login.status_code == 200, login.text
        owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        menu = await client.get(f"/api/v1/branches/{branch_id}/menu")
        assert menu.status_code == 200, menu.text
        category = await client.post(
            f"/api/v1/branches/{branch_id}/menu/categories",
            json={"name": "Meals"},
            headers=owner_headers,
        )
        assert category.status_code == 201, category.text
        dish = await client.post(
            f"/api/v1/branches/{branch_id}/menu/items",
            json={
                "category_id": category.json()["id"],
                "name": "Journey Meal",
                "base_price": 42.50,
            },
            headers=owner_headers,
        )
        assert dish.status_code == 201, dish.text
        stock = await client.post(
            f"/api/v1/branches/{branch_id}/inventory",
            json={"menu_item_id": dish.json()["id"], "initial_quantity": 3},
            headers=owner_headers,
        )
        assert stock.status_code == 201, stock.text
        order_payload = {
            "branch_id": branch_id,
            "items": [{"menu_item_id": dish.json()["id"], "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Test"},
        }
        customer_headers = ctx["headers"][0]
        placed = await client.post(
            "/api/v1/orders", json=order_payload, headers=customer_headers
        )
        assert placed.status_code == 201, placed.text
        retry = await client.post(
            "/api/v1/orders", json=order_payload, headers=customer_headers
        )
        assert retry.status_code == 201 and retry.json()["id"] == placed.json()["id"]
        changed = await client.post(
            "/api/v1/orders",
            json={
                **order_payload,
                "items": [{"menu_item_id": dish.json()["id"], "quantity": 2}],
            },
            headers=customer_headers,
        )
        assert changed.status_code == 409
        order_id = placed.json()["id"]
        own = await client.get(f"/api/v1/orders/{order_id}", headers=owner_headers)
        foreign = await client.get(
            f"/api/v1/orders/{order_id}", headers=ctx["owner_headers"]
        )
        assert own.status_code == 200 and foreign.status_code == 403
        accepted = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "ACCEPTED"},
            headers=owner_headers,
        )
        assert accepted.status_code == 200, accepted.text
        cancelled = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=owner_headers
        )
        assert cancelled.status_code == 200, cancelled.text
        second_cancel = await client.post(
            f"/api/v1/orders/{order_id}/cancel", headers=owner_headers
        )
        assert second_cancel.status_code == 400
    async with ctx["sessions"]() as session:
        row = await session.get(InventoryItem, uuid.UUID(stock.json()["id"]))
        assert row.quantity == 3 and row.is_in_stock is True
        holds = (
            await session.scalars(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(order_id)
                )
            )
        ).all()
        assert len(holds) == 1 and holds[0].released_at is not None
