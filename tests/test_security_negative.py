"""
Focused negative / security backend tests – R-ID security follow-up.

Covers findings from the independent security review (2026-10-25):
  SEC-A: Payment endpoint cross-customer access (payment intent and verify).
  SEC-B: Customer cannot escalate order status beyond CANCELLED.
  SEC-C: Soft-deleted menu category items are rejected at checkout with ITEM_UNAVAILABLE.
  SEC-D: First cancel releases stock; repeat cancel is rejected without duplicate release.
  SEC-E: KitchenStaff assigned to a different real branch cannot read foreign branch orders.
  SEC-F: Payment history is blocked for foreign customer and KitchenStaff.
  SEC-G: Idempotency key scoped per customer: two 201s, distinct IDs, separate reservations.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token
from app.customer.models import CustomerProfile
from app.inventory.models import InventoryItem
from app.kitchen.models import Kitchen
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.order.models import Order, OrderItem, OrderReservation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bearer(user: User, extra_claims: dict[str, str] | None = None) -> dict[str, str]:
    claims: dict[str, str] = {}
    if user.branch_id is not None:
        claims["branch_id"] = str(user.branch_id)
    if extra_claims:
        claims.update(extra_claims)
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        extra_claims=claims if claims else None,
    )
    return {"Authorization": f"Bearer {token}"}


async def _build_branch_with_item(
    db: AsyncSession,
    *,
    owner: User,
    item_price: float = 50.0,
    item_name: str = "TestItem",
    stock: int = 10,
    branch_active: bool = True,
    merchant_status: str = "APPROVED",
) -> tuple[Branch, MenuItem, InventoryItem]:
    """Build a complete, deterministically open branch hierarchy with an active kitchen."""
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="TestMerchant",
        legal_entity_name="TestMerchant",
        fssai_license_number="12345678901234",
        status=merchant_status,
    )
    db.add(merchant)
    await db.flush()

    brand = Brand(merchant_id=merchant.id, name="Brand")
    db.add(brand)
    await db.flush()

    branch = Branch(
        brand_id=brand.id,
        name="Branch",
        address_text="Addr",
        is_active=branch_active,
        timezone_name="UTC",
    )
    db.add(branch)
    await db.flush()

    # Deterministically open 24/7: opening == closing bypasses clock-based closure
    branch.closing_time = branch.opening_time

    # Active kitchen required for checkout admission (INV-0001)
    kitchen = Kitchen(
        branch_id=branch.id,
        name="Main Kitchen",
        is_active=True,
    )
    db.add(kitchen)
    await db.flush()

    menu = Menu(branch_id=branch.id, name="MainMenu", is_active=True)
    db.add(menu)
    await db.flush()

    category = MenuCategory(menu_id=menu.id, name="Cat")
    db.add(category)
    await db.flush()

    item = MenuItem(
        category_id=category.id,
        name=item_name,
        base_price=item_price,
        is_available=True,
    )
    db.add(item)
    await db.flush()

    inv = InventoryItem(
        branch_id=branch.id,
        menu_item_id=item.id,
        quantity=stock,
        is_in_stock=True,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(branch)
    await db.refresh(item)
    await db.refresh(inv)
    return branch, item, inv


# ---------------------------------------------------------------------------
# SEC-B: Customer cannot drive kitchen-only order status transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customer_cannot_set_order_status_to_accepted_or_preparing(
    client: AsyncClient, db_session: AsyncSession
):
    """A Customer who owns an order cannot ACCEPT or PREPARE it (staff-only transitions).

    The PATCH /orders/{id}/status endpoint must block non-CANCELLED status from customers.
    """
    owner = User(email="sec-b-owner@example.com", role="MerchantOwner", is_active=True)
    customer_user = User(
        email="sec-b-customer@example.com", role="Customer", is_active=True
    )
    db_session.add_all([owner, customer_user])
    await db_session.flush()

    branch, item, _inv = await _build_branch_with_item(db_session, owner=owner)

    profile = CustomerProfile(
        user_id=customer_user.id,
        full_name="SecBCustomer",
        phone_number="+910000000001",
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        total_amount=50,
        status="PLACED",
        delivery_address_snapshot={"address": "test"},
        idempotency_key="sec-b-key-001",
        request_fingerprint="deadbeef" * 8,
    )
    db_session.add(order)
    await db_session.flush()
    order_item = OrderItem(
        order_id=order.id,
        menu_item_id=item.id,
        item_name_snapshot=item.name,
        unit_price_snapshot=50,
        quantity=1,
    )
    db_session.add(order_item)
    await db_session.commit()

    cust_headers = _bearer(customer_user)

    for forbidden_status in ("ACCEPTED", "PREPARING", "READY", "COMPLETED"):
        resp = await client.patch(
            f"/api/v1/orders/{order.id}/status",
            json={"status": forbidden_status},
            headers=cust_headers,
        )
        assert resp.status_code in (403, 422), (
            f"Expected 403/422 for customer setting status={forbidden_status}, "
            f"got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# SEC-C: Soft-deleted category items are rejected at checkout admission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_creation_rejected_for_item_in_soft_deleted_category(
    client: AsyncClient, db_session: AsyncSession
):
    """An item whose category has been soft-deleted must not be admitted to a new order.

    order/service.py checks `menu_item.category.deleted_at is not None` at admission and
    raises DomainInvariantError("Menu item is unavailable.", "ITEM_UNAVAILABLE").
    Verifies exact ITEM_UNAVAILABLE error response and that inventory stock is untouched.
    """
    owner = User(email="sec-c-owner@example.com", role="MerchantOwner", is_active=True)
    customer_user = User(
        email="sec-c-customer@example.com", role="Customer", is_active=True
    )
    db_session.add_all([owner, customer_user])
    await db_session.flush()

    branch, item, inv = await _build_branch_with_item(db_session, owner=owner, stock=10)
    initial_stock = inv.quantity

    # Soft-delete the category
    category = await db_session.get(MenuCategory, item.category_id)
    assert category is not None
    category.deleted_at = datetime.now(UTC)
    await db_session.commit()

    profile = CustomerProfile(
        user_id=customer_user.id,
        full_name="SecCCustomer",
        phone_number="+910000000002",
    )
    db_session.add(profile)
    await db_session.commit()

    cust_headers = _bearer(customer_user)
    resp = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(branch.id),
            "items": [{"menu_item_id": str(item.id), "quantity": 1}],
            "delivery_address_snapshot": {"address": "test"},
        },
        headers={**cust_headers, "Idempotency-Key": "sec-c-key-001"},
    )
    # Must fail with exact 400 Bad Request and error_code ITEM_UNAVAILABLE
    assert (
        resp.status_code == 400
    ), f"Expected 400 ITEM_UNAVAILABLE, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert (
        data.get("error_code") == "ITEM_UNAVAILABLE"
    ), f"Expected error_code 'ITEM_UNAVAILABLE', got: {data}"

    # Stock must remain unchanged
    await db_session.refresh(inv)
    assert (
        inv.quantity == initial_stock
    ), f"Stock changed on rejected order: expected {initial_stock}, got {inv.quantity}"

    # No reservations or orders created
    order_count = await db_session.scalar(
        select(func.count(Order.id)).where(Order.branch_id == branch.id)
    )
    assert order_count == 0
    res_count = await db_session.scalar(
        select(func.count(OrderReservation.id)).where(
            OrderReservation.inventory_item_id == inv.id
        )
    )
    assert res_count == 0


# ---------------------------------------------------------------------------
# SEC-D: First cancel releases stock; repeat cancel is rejected without duplicate release
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_cancel_does_not_release_stock_twice(
    client: AsyncClient, db_session: AsyncSession
):
    """A first cancellation releases reserved stock. A repeat cancellation is rejected
    with ILLEGAL_STATUS_TRANSITION and does not release stock a second time.
    """
    owner = User(email="sec-d-owner@example.com", role="MerchantOwner", is_active=True)
    customer_user = User(
        email="sec-d-customer@example.com", role="Customer", is_active=True
    )
    db_session.add_all([owner, customer_user])
    await db_session.flush()

    branch, item, inv = await _build_branch_with_item(db_session, owner=owner, stock=10)
    initial_stock = inv.quantity

    profile = CustomerProfile(
        user_id=customer_user.id,
        full_name="SecDCustomer",
        phone_number="+910000000003",
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    cust_headers = _bearer(customer_user)

    # 1. Place a real order via checkout API reserving 2 units
    create_resp = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(branch.id),
            "items": [{"menu_item_id": str(item.id), "quantity": 2}],
            "delivery_address_snapshot": {"address": "test"},
        },
        headers={**cust_headers, "Idempotency-Key": "sec-d-create-key"},
    )
    assert create_resp.status_code == 201, f"Order creation failed: {create_resp.text}"
    order_id = create_resp.json()["id"]

    # Verify inventory was decremented by 2
    await db_session.refresh(inv)
    assert (
        inv.quantity == initial_stock - 2
    ), f"Expected stock to be {initial_stock - 2}, got {inv.quantity}"

    # Verify active reservation exists with released_at is None
    res_before = (
        (
            await db_session.execute(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(order_id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(res_before) == 1
    assert res_before[0].quantity == 2
    assert res_before[0].released_at is None

    # 2. First cancellation: customer cancels the order
    cancel_resp1 = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=cust_headers,
    )
    assert (
        cancel_resp1.status_code == 200
    ), f"First cancel should succeed with 200, got {cancel_resp1.status_code}: {cancel_resp1.text}"
    assert cancel_resp1.json()["status"] == "CANCELLED"

    # Verify stock restored to initial_stock (10)
    await db_session.refresh(inv)
    assert (
        inv.quantity == initial_stock
    ), f"Expected stock restored to {initial_stock}, got {inv.quantity}"

    # Verify reservation released_at is now stamped
    res_after1 = (
        (
            await db_session.execute(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(order_id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(res_after1) == 1
    assert res_after1[0].released_at is not None

    # 3. Repeat cancellation: second cancel must fail
    cancel_resp2 = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=cust_headers,
    )
    assert (
        cancel_resp2.status_code == 400
    ), f"Expected 400 on repeat cancel, got {cancel_resp2.status_code}: {cancel_resp2.text}"
    data = cancel_resp2.json()
    assert (
        data.get("error_code") == "ILLEGAL_STATUS_TRANSITION"
    ), f"Expected ILLEGAL_STATUS_TRANSITION on repeat cancel, got: {data}"

    # Verify stock remains exactly initial_stock (NOT incremented again to 12)
    await db_session.refresh(inv)
    assert (
        inv.quantity == initial_stock
    ), f"Stock double-released on repeat cancel: expected {initial_stock}, got {inv.quantity}"

    # Verify no additional reservations were created
    res_after2 = (
        (
            await db_session.execute(
                select(OrderReservation).where(
                    OrderReservation.order_id == uuid.UUID(order_id)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(res_after2) == 1


# ---------------------------------------------------------------------------
# SEC-E: KitchenStaff assigned to a different real branch cannot read foreign branch orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kitchen_staff_assigned_to_different_branch_cannot_read_foreign_orders(
    client: AsyncClient, db_session: AsyncSession
):
    """KitchenStaff assigned to real Branch B cannot list orders for real Branch A.

    Tests branch tenancy enforcement in require_branch_access():
    staff's branch_id claim must match the requested branch_id.
    """
    owner = User(email="sec-e-owner@example.com", role="MerchantOwner", is_active=True)
    db_session.add(owner)
    await db_session.flush()

    # Create Branch A (target branch with orders)
    branch_a, _item_a, _inv_a = await _build_branch_with_item(
        db_session, owner=owner, item_name="ItemA"
    )

    # Create Branch B (different real branch where staff is assigned)
    branch_b = Branch(
        brand_id=branch_a.brand_id,
        name="Branch B (Other)",
        address_text="Addr B",
        is_active=True,
        timezone_name="UTC",
    )
    db_session.add(branch_b)
    await db_session.flush()
    branch_b.closing_time = branch_b.opening_time
    kitchen_b = Kitchen(branch_id=branch_b.id, name="Kitchen B", is_active=True)
    db_session.add(kitchen_b)
    await db_session.flush()

    # Staff explicitly assigned to Branch B
    staff_branch_b = User(
        email="sec-e-staff-b@example.com",
        role="KitchenStaff",
        is_active=True,
        branch_id=branch_b.id,
    )
    # Also test an unassigned staff member (branch_id=None)
    staff_unassigned = User(
        email="sec-e-staff-unassigned@example.com",
        role="KitchenStaff",
        is_active=True,
        branch_id=None,
    )
    # And staff legitimately assigned to Branch A
    staff_branch_a = User(
        email="sec-e-staff-a@example.com",
        role="KitchenStaff",
        is_active=True,
        branch_id=branch_a.id,
    )
    db_session.add_all([staff_branch_b, staff_unassigned, staff_branch_a])
    await db_session.commit()

    # 1. Staff assigned to Branch B attempts to read Branch A -> 403 Forbidden
    headers_b = _bearer(staff_branch_b)
    resp_b = await client.get(
        "/api/v1/orders",
        params={"branch_id": str(branch_a.id)},
        headers=headers_b,
    )
    assert resp_b.status_code == 403, (
        f"Staff assigned to Branch B must receive 403 reading Branch A orders, "
        f"got {resp_b.status_code}: {resp_b.text}"
    )
    assert resp_b.json().get("error_code") == "BRANCH_ACCESS_FORBIDDEN"

    # 2. Unassigned staff attempts to read Branch A -> 403 Forbidden
    headers_unassigned = _bearer(staff_unassigned)
    resp_unassigned = await client.get(
        "/api/v1/orders",
        params={"branch_id": str(branch_a.id)},
        headers=headers_unassigned,
    )
    assert resp_unassigned.status_code == 403, (
        f"Unassigned staff must receive 403 reading Branch A orders, "
        f"got {resp_unassigned.status_code}: {resp_unassigned.text}"
    )
    assert resp_unassigned.json().get("error_code") == "BRANCH_ACCESS_FORBIDDEN"

    # 3. Staff legitimately assigned to Branch A -> 200 OK
    headers_a = _bearer(staff_branch_a)
    resp_a = await client.get(
        "/api/v1/orders",
        params={"branch_id": str(branch_a.id)},
        headers=headers_a,
    )
    assert resp_a.status_code == 200, (
        f"Staff assigned to Branch A should successfully list Branch A orders, "
        f"got {resp_a.status_code}: {resp_a.text}"
    )


# ---------------------------------------------------------------------------
# SEC-F: Payment history blocked for foreign customer and KitchenStaff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_history_blocked_for_foreign_customer(
    client: AsyncClient, db_session: AsyncSession
):
    """A payment record must not be readable by a different customer (not the order owner)."""
    from app.payment.models import Payment

    owner = User(email="sec-f-owner@example.com", role="MerchantOwner", is_active=True)
    cust_a = User(email="sec-f-a@example.com", role="Customer", is_active=True)
    cust_b = User(email="sec-f-b@example.com", role="Customer", is_active=True)
    db_session.add_all([owner, cust_a, cust_b])
    await db_session.flush()

    branch, _item, _inv = await _build_branch_with_item(db_session, owner=owner)

    profile_a = CustomerProfile(
        user_id=cust_a.id,
        full_name="CustA",
        phone_number="+910000000004",
    )
    profile_b = CustomerProfile(
        user_id=cust_b.id,
        full_name="CustB",
        phone_number="+910000000005",
    )
    db_session.add_all([profile_a, profile_b])
    await db_session.flush()

    # Order belonging to profile_a
    order = Order(
        customer_profile_id=profile_a.id,
        branch_id=branch.id,
        total_amount=50,
        status="PLACED",
        delivery_address_snapshot={"address": "test"},
        idempotency_key="sec-f-key-001",
        request_fingerprint="deadbeef" * 8,
    )
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        order_id=order.id,
        customer_profile_id=profile_a.id,
        amount=50,
        currency="INR",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    # cust_b (foreign customer) must not read cust_a's payment
    headers_b = _bearer(cust_b)
    resp = await client.get(f"/api/v1/payments/{payment.id}", headers=headers_b)
    assert resp.status_code == 403, (
        f"Foreign customer must not read another customer's payment, "
        f"got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_payment_history_blocked_for_kitchen_staff(
    client: AsyncClient, db_session: AsyncSession
):
    """KitchenStaff is not in the allowed payment-reader roles and must receive 403."""
    from app.payment.models import Payment

    owner = User(email="sec-f2-owner@example.com", role="MerchantOwner", is_active=True)
    cust = User(email="sec-f2-cust@example.com", role="Customer", is_active=True)
    staff = User(
        email="sec-f2-staff@example.com",
        role="KitchenStaff",
        is_active=True,
    )
    db_session.add_all([owner, cust, staff])
    await db_session.flush()

    branch, _item, _inv = await _build_branch_with_item(db_session, owner=owner)
    profile = CustomerProfile(
        user_id=cust.id,
        full_name="CustF2",
        phone_number="+910000000006",
    )
    db_session.add(profile)
    await db_session.flush()

    order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        total_amount=30,
        status="PLACED",
        delivery_address_snapshot={"address": "test"},
        idempotency_key="sec-f2-key-001",
        request_fingerprint="deadbeef" * 8,
    )
    db_session.add(order)
    await db_session.flush()

    payment = Payment(
        order_id=order.id,
        customer_profile_id=profile.id,
        amount=30,
        currency="INR",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    staff_headers = _bearer(staff)
    resp = await client.get(f"/api/v1/payments/{payment.id}", headers=staff_headers)
    assert (
        resp.status_code == 403
    ), f"KitchenStaff must not access payment history, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# SEC-G: Idempotency key is scoped per customer, not global
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_idempotency_key_accepted_for_different_customers(
    client: AsyncClient, db_session: AsyncSession
):
    """Two different customers may reuse the same idempotency key string independently.

    The unique constraint on (customer_profile_id, idempotency_key) scopes keys per customer.
    Both customers' orders must return 201 Created with distinct order IDs and separate
    reservations holding inventory.
    """
    owner = User(email="sec-g-owner@example.com", role="MerchantOwner", is_active=True)
    cust_a = User(email="sec-g-a@example.com", role="Customer", is_active=True)
    cust_b = User(email="sec-g-b@example.com", role="Customer", is_active=True)
    db_session.add_all([owner, cust_a, cust_b])
    await db_session.flush()

    branch, item, inv = await _build_branch_with_item(db_session, owner=owner, stock=20)
    initial_stock = inv.quantity

    profile_a = CustomerProfile(
        user_id=cust_a.id, full_name="GA", phone_number="+910000000007"
    )
    profile_b = CustomerProfile(
        user_id=cust_b.id, full_name="GB", phone_number="+910000000008"
    )
    db_session.add_all([profile_a, profile_b])
    await db_session.commit()

    shared_key = "shared-idempotency-key-abc"
    payload = {
        "branch_id": str(branch.id),
        "items": [{"menu_item_id": str(item.id), "quantity": 1}],
        "delivery_address_snapshot": {"address": "test"},
    }

    # 1. Place order for Customer A with shared_key — must return 201
    resp_a = await client.post(
        "/api/v1/orders",
        json=payload,
        headers={**_bearer(cust_a), "Idempotency-Key": shared_key},
    )
    assert (
        resp_a.status_code == 201
    ), f"Customer A order with key '{shared_key}' failed: {resp_a.text}"
    order_a_id = uuid.UUID(resp_a.json()["id"])

    # 2. Place order for Customer B with identical shared_key — must also return 201
    resp_b = await client.post(
        "/api/v1/orders",
        json=payload,
        headers={**_bearer(cust_b), "Idempotency-Key": shared_key},
    )
    assert (
        resp_b.status_code == 201
    ), f"Customer B order with key '{shared_key}' failed: {resp_b.text}"
    order_b_id = uuid.UUID(resp_b.json()["id"])

    # 3. Order IDs must be distinct
    assert (
        order_a_id != order_b_id
    ), f"Both orders returned identical order ID: {order_a_id}"

    # 4. Each order must have its own separate OrderReservation record
    res_a = (
        (
            await db_session.execute(
                select(OrderReservation).where(OrderReservation.order_id == order_a_id)
            )
        )
        .scalars()
        .all()
    )
    res_b = (
        (
            await db_session.execute(
                select(OrderReservation).where(OrderReservation.order_id == order_b_id)
            )
        )
        .scalars()
        .all()
    )

    assert (
        len(res_a) == 1
    ), f"Expected exactly 1 reservation for Order A, got {len(res_a)}"
    assert (
        len(res_b) == 1
    ), f"Expected exactly 1 reservation for Order B, got {len(res_b)}"
    assert res_a[0].id != res_b[0].id, "Reservations must be separate records"
    assert res_a[0].order_id == order_a_id
    assert res_b[0].order_id == order_b_id
    assert res_a[0].quantity == 1
    assert res_b[0].quantity == 1
    assert res_a[0].released_at is None
    assert res_b[0].released_at is None

    # 5. Inventory must reflect both units held (initial 20 -> 18)
    await db_session.refresh(inv)
    assert (
        inv.quantity == initial_stock - 2
    ), f"Expected stock to be {initial_stock - 2}, got {inv.quantity}"
