import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant


@pytest.fixture
async def setup_order_fixture(db_session: AsyncSession):
    """Helper fixture for Order tests."""
    cust_user = User(
        email="ord_cust@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    staff_user = User(
        email="ord_staff@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="KitchenStaff",
        is_active=True,
    )
    db_session.add_all([cust_user, staff_user])
    await db_session.flush()

    cust_profile = CustomerProfile(
        user_id=cust_user.id,
        full_name="Order Customer",
        phone_number="9988776655",
    )
    db_session.add(cust_profile)
    await db_session.flush()

    merchant = Merchant(
        owner_user_id=staff_user.id,
        business_name="Order Merchant",
        legal_entity_name="Order Merchant LLC",
        fssai_license_number="11223344556677",
        status="APPROVED",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Order Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(
        brand_id=brand.id, name="Order Branch", address_text="Campus Gate 1"
    )
    branch_other = Branch(
        brand_id=brand.id, name="Other Branch", address_text="Campus Gate 2"
    )
    db_session.add_all([branch, branch_other])
    await db_session.flush()
    branch.closing_time = branch.opening_time
    staff_user.branch_id = branch.id

    menu = Menu(branch_id=branch.id, name="Main Menu")
    menu_other = Menu(branch_id=branch_other.id, name="Other Menu")
    db_session.add_all([menu, menu_other])
    await db_session.flush()

    category = MenuCategory(menu_id=menu.id, name="Beverages")
    category_other = MenuCategory(menu_id=menu_other.id, name="Snacks")
    db_session.add_all([category, category_other])
    await db_session.flush()

    item_1 = MenuItem(category_id=category.id, name="Cold Coffee", base_price=80.00)
    item_2 = MenuItem(category_id=category.id, name="Hot Tea", base_price=30.00)
    item_other = MenuItem(
        category_id=category_other.id, name="Foreign Cookie", base_price=50.00
    )
    db_session.add_all([item_1, item_2, item_other])
    await db_session.flush()
    db_session.add(Kitchen(branch_id=branch.id, name="Main Kitchen", is_active=True))
    db_session.add_all(
        [
            InventoryItem(
                branch_id=branch.id,
                menu_item_id=item_1.id,
                quantity=10,
                is_in_stock=True,
            ),
            InventoryItem(
                branch_id=branch.id,
                menu_item_id=item_2.id,
                quantity=10,
                is_in_stock=True,
            ),
        ]
    )
    await db_session.commit()

    cust_token = create_access_token(subject=str(cust_user.id), role=cust_user.role)
    staff_token = create_access_token(subject=str(staff_user.id), role=staff_user.role)

    return {
        "cust_user": cust_user,
        "cust_profile": cust_profile,
        "staff_user": staff_user,
        "branch": branch,
        "branch_other": branch_other,
        "item_1": item_1,
        "item_2": item_2,
        "item_other": item_other,
        "cust_headers": {
            "Authorization": f"Bearer {cust_token}",
            "Idempotency-Key": "order-fixture-key",
        },
        "staff_headers": {"Authorization": f"Bearer {staff_token}"},
    }


@pytest.mark.asyncio
async def test_order_creation_flow(client: AsyncClient, setup_order_fixture: dict):
    ctx = setup_order_fixture
    branch_id = ctx["branch"].id
    headers = ctx["cust_headers"]

    payload = {
        "branch_id": str(branch_id),
        "items": [
            {"menu_item_id": str(ctx["item_1"].id), "quantity": 2},
            {"menu_item_id": str(ctx["item_2"].id), "quantity": 1},
        ],
        "delivery_address_snapshot": {"address_line": "Room 402, Block B"},
    }

    response = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["branch_id"] == str(branch_id)
    assert data["status"] == "PLACED"
    assert data["total_amount"] == 190.00  # (80 * 2) + 30
    assert len(data["items"]) == 2
    assert len(data["status_logs"]) == 1
    assert data["status_logs"][0]["new_status"] == "PLACED"


@pytest.mark.asyncio
async def test_order_single_branch_constraint(
    client: AsyncClient, setup_order_fixture: dict
):
    ctx = setup_order_fixture
    branch_id = ctx["branch"].id
    headers = ctx["cust_headers"]

    # Attempting to include item_other (belonging to branch_other)
    payload = {
        "branch_id": str(branch_id),
        "items": [
            {"menu_item_id": str(ctx["item_1"].id), "quantity": 1},
            {"menu_item_id": str(ctx["item_other"].id), "quantity": 1},
        ],
        "delivery_address_snapshot": {"address_line": "Room 402, Block B"},
    }

    response = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()["error_code"] == "CROSS_BRANCH_ORDER_VIOLATION"


@pytest.mark.asyncio
async def test_order_state_transitions(client: AsyncClient, setup_order_fixture: dict):
    ctx = setup_order_fixture
    branch_id = ctx["branch"].id
    headers = ctx["cust_headers"]
    staff_headers = ctx["staff_headers"]

    # 1. Create Order (PLACED)
    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(branch_id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=headers,
    )
    order_id = create_res.json()["id"]

    # 2. PLACED -> ACCEPTED
    res1 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "ACCEPTED"},
        headers=staff_headers,
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "ACCEPTED"

    # 3. ACCEPTED -> PREPARING
    res2 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "PREPARING"},
        headers=staff_headers,
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "PREPARING"

    # 4. PREPARING -> READY
    res3 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "READY"},
        headers=staff_headers,
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "READY"

    # 5. READY -> COMPLETED
    res4 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "COMPLETED"},
        headers=staff_headers,
    )
    assert res4.status_code == 200
    assert res4.json()["status"] == "COMPLETED"
    assert len(res4.json()["status_logs"]) >= 4


@pytest.mark.asyncio
async def test_illegal_state_transition(client: AsyncClient, setup_order_fixture: dict):
    ctx = setup_order_fixture
    branch_id = ctx["branch"].id
    headers = ctx["cust_headers"]
    staff_headers = ctx["staff_headers"]

    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(branch_id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=headers,
    )
    order_id = create_res.json()["id"]

    # Attempt illegal transition: PLACED -> READY
    illegal_res = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "READY"},
        headers=staff_headers,
    )
    assert illegal_res.status_code == 400
    assert illegal_res.json()["error_code"] == "ILLEGAL_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_order_cancellation(client: AsyncClient, setup_order_fixture: dict):
    ctx = setup_order_fixture
    branch_id = ctx["branch"].id
    headers = ctx["cust_headers"]

    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(branch_id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=headers,
    )
    order_id = create_res.json()["id"]

    cancel_res = await client.post(f"/api/v1/orders/{order_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_retry_is_same_order_and_changed_payload_conflicts(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    ctx = setup_order_fixture
    payload = {
        "branch_id": str(ctx["branch"].id),
        "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Hostel 2"},
    }
    first = await client.post(
        "/api/v1/orders", json=payload, headers=ctx["cust_headers"]
    )
    retry = await client.post(
        "/api/v1/orders", json=payload, headers=ctx["cust_headers"]
    )
    assert first.status_code == retry.status_code == 201
    assert first.json()["id"] == retry.json()["id"]
    from sqlalchemy import select

    stock = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    assert stock == 9
    payload["items"][0]["quantity"] = 2
    changed = await client.post(
        "/api/v1/orders", json=payload, headers=ctx["cust_headers"]
    )
    assert changed.status_code == 409
    assert changed.json()["error_code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_last_unit_and_cancellation_release_once(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    from sqlalchemy import select

    ctx = setup_order_fixture
    inventory = await db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    inventory.quantity = 1
    await db_session.commit()
    payload = {
        "branch_id": str(ctx["branch"].id),
        "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
        "delivery_address_snapshot": {"address_line": "Hostel 2"},
    }
    first = await client.post(
        "/api/v1/orders", json=payload, headers=ctx["cust_headers"]
    )
    assert first.status_code == 201
    headers = {**ctx["cust_headers"], "Idempotency-Key": "different-order-key"}
    second = await client.post("/api/v1/orders", json=payload, headers=headers)
    assert second.status_code == 400
    assert second.json()["error_code"] == "INSUFFICIENT_STOCK"
    await db_session.refresh(inventory)
    assert inventory.quantity == 0
    cancelled = await client.post(
        f"/api/v1/orders/{first.json()['id']}/cancel", headers=ctx["cust_headers"]
    )
    assert cancelled.status_code == 200
    repeated = await client.post(
        f"/api/v1/orders/{first.json()['id']}/cancel", headers=ctx["cust_headers"]
    )
    assert repeated.status_code == 400
    await db_session.refresh(inventory)
    assert inventory.quantity == 1


@pytest.mark.asyncio
async def test_customer_cannot_cancel_accepted_order_via_post_cancel(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    from sqlalchemy import select

    ctx = setup_order_fixture
    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=ctx["cust_headers"],
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # Staff marks ACCEPTED
    accept_res = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "ACCEPTED"},
        headers=ctx["staff_headers"],
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "ACCEPTED"

    # Record stock level before cancel attempt
    stock_before = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )

    # Customer attempts POST cancel on ACCEPTED order
    cancel_res = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=ctx["cust_headers"],
    )
    assert cancel_res.status_code == 400
    assert cancel_res.json()["error_code"] == "CUSTOMER_CANCELLATION_WINDOW_EXPIRED"

    # Stock must remain unchanged
    stock_after = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    assert stock_after == stock_before


@pytest.mark.asyncio
async def test_customer_cannot_cancel_accepted_order_via_patch_status(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    from sqlalchemy import select

    ctx = setup_order_fixture
    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=ctx["cust_headers"],
    )
    assert create_res.status_code == 201
    order_id = create_res.json()["id"]

    # Staff marks ACCEPTED
    accept_res = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "ACCEPTED"},
        headers=ctx["staff_headers"],
    )
    assert accept_res.status_code == 200

    stock_before = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )

    # Customer attempts PATCH status -> CANCELLED
    patch_cancel = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "CANCELLED"},
        headers=ctx["cust_headers"],
    )
    assert patch_cancel.status_code == 400
    assert patch_cancel.json()["error_code"] == "CUSTOMER_CANCELLATION_WINDOW_EXPIRED"

    # Stock must remain unchanged
    stock_after = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    assert stock_after == stock_before


@pytest.mark.asyncio
async def test_staff_can_cancel_accepted_order(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    from sqlalchemy import select

    ctx = setup_order_fixture
    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=ctx["cust_headers"],
    )
    order_id = create_res.json()["id"]

    # Staff marks ACCEPTED
    await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "ACCEPTED"},
        headers=ctx["staff_headers"],
    )

    stock_before = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )

    # Staff cancels ACCEPTED order
    cancel_res = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=ctx["staff_headers"],
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Stock released exactly once
    stock_after = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    assert stock_after == stock_before + 1


@pytest.mark.asyncio
async def test_staff_can_cancel_placed_order(
    client: AsyncClient, setup_order_fixture: dict, db_session: AsyncSession
):
    from sqlalchemy import select

    ctx = setup_order_fixture
    create_res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=ctx["cust_headers"],
    )
    order_id = create_res.json()["id"]

    stock_before = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )

    # Staff cancels PLACED order
    cancel_res = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=ctx["staff_headers"],
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Stock released exactly once
    stock_after = await db_session.scalar(
        select(InventoryItem.quantity).where(
            InventoryItem.branch_id == ctx["branch"].id,
            InventoryItem.menu_item_id == ctx["item_1"].id,
        )
    )
    assert stock_after == stock_before + 1
