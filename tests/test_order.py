import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers, QueryParams

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.exceptions import ForbiddenError
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.order.router import authenticate_websocket


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
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Order Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(brand_id=brand.id, name="Order Branch", address_text="Campus Gate 1")
    branch_other = Branch(brand_id=brand.id, name="Other Branch", address_text="Campus Gate 2")
    db_session.add_all([branch, branch_other])
    await db_session.flush()

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
    item_other = MenuItem(category_id=category_other.id, name="Foreign Cookie", base_price=50.00)
    db_session.add_all([item_1, item_2, item_other])
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
        "cust_headers": {"Authorization": f"Bearer {cust_token}"},
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
async def test_order_single_branch_constraint(client: AsyncClient, setup_order_fixture: dict):
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
async def test_order_detail_rejects_other_customer(
    client: AsyncClient, db_session: AsyncSession, setup_order_fixture: dict
):
    ctx = setup_order_fixture
    created = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item_1"].id), "quantity": 1}],
            "delivery_address_snapshot": {"address_line": "Hostel 2"},
        },
        headers=ctx["cust_headers"],
    )
    other = User(
        email="otherorder@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(CustomerProfile(user_id=other.id, full_name="Other Customer"))
    await db_session.commit()
    token = create_access_token(subject=str(other.id), role=other.role)
    denied = await client.get(
        f"/api/v1/orders/{created.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "ORDER_ACCESS_FORBIDDEN"


@pytest.mark.asyncio
async def test_websocket_auth_helper_accepts_authorized_branch_token(
    db_session: AsyncSession, setup_order_fixture: dict
):
    ctx = setup_order_fixture
    token = create_access_token(subject=str(ctx["staff_user"].id), role=ctx["staff_user"].role)

    class FakeWebSocket:
        query_params = QueryParams({"access_token": token})
        headers = Headers()

    claims = await authenticate_websocket(
        FakeWebSocket(),
        ctx["branch"].id,
        db_session,  # type: ignore[arg-type]
    )
    assert claims.sub == str(ctx["staff_user"].id)


@pytest.mark.asyncio
async def test_websocket_auth_rejects_missing_token_and_customer_role(
    db_session: AsyncSession, setup_order_fixture: dict
):
    ctx = setup_order_fixture

    class MissingTokenWebSocket:
        query_params = QueryParams()
        headers = Headers()

    with pytest.raises(ForbiddenError, match="access token required"):
        await authenticate_websocket(
            MissingTokenWebSocket(),
            ctx["branch"].id,
            db_session,  # type: ignore[arg-type]
        )

    customer_token = create_access_token(
        subject=str(ctx["cust_user"].id), role=ctx["cust_user"].role
    )

    class CustomerWebSocket:
        query_params = QueryParams({"access_token": customer_token})
        headers = Headers()

    with pytest.raises(ForbiddenError, match="access denied"):
        await authenticate_websocket(
            CustomerWebSocket(),
            ctx["branch"].id,
            db_session,  # type: ignore[arg-type]
        )
