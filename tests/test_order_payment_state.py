"""Orders wait for payment before the restaurant can see them.

An order is created as PENDING_PAYMENT. The kitchen cannot see it, cannot be beeped by it and
cannot cook it. When the payment is confirmed it becomes PLACED, and only then do the kitchen
screens hear about it. These tests drive the real order and payment endpoints.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token, hash_password
from app.credit.service import StoreCreditService
from app.customer.models import CustomerProfile
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.notification.models import Notification
from app.order.models import Order
from app.order.websocket_manager import ws_manager
from app.payment.models import Payment, PaymentTransaction
from app.payment.razorpay_adapter import RazorpayAdapter
from tests.conftest import pay_for_order

PRICE = 100.0


def _token(user: User, role: str) -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject=str(user.id), role=role)}"
    }


@pytest.fixture
async def shop(db_session: AsyncSession) -> dict:
    users = {}
    for key, role in (
        ("cust", "Customer"),
        ("cust2", "Customer"),
        ("staff", "KitchenStaff"),
        ("admin", "PlatformAdmin"),
    ):
        user = User(
            email=f"{key}@pending.test",
            password_hash=hash_password("Password123!"),
            role=role,
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        users[key] = user
    await db_session.flush()
    profile = CustomerProfile(user_id=users["cust"].id, full_name="Asha Kumar")
    profile2 = CustomerProfile(user_id=users["cust2"].id, full_name="Ravi Rao")
    merchant = Merchant(
        owner_user_id=users["staff"].id,
        business_name="Pending Merchant",
        legal_entity_name="Pending Merchant LLC",
        fssai_license_number="55667788990011",
    )
    db_session.add_all([profile, profile2, merchant])
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Pending Brand")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Food Court", address_text="Gate 1")
    db_session.add(branch)
    await db_session.flush()
    menu = Menu(branch_id=branch.id, name="Main")
    db_session.add(menu)
    await db_session.flush()
    category = MenuCategory(menu_id=menu.id, name="Meals")
    db_session.add(category)
    await db_session.flush()
    item = MenuItem(category_id=category.id, name="Biryani", base_price=PRICE)
    db_session.add(item)
    await db_session.commit()
    return {
        "users": users,
        "profile": profile,
        "profile2": profile2,
        "brand": brand,
        "branch": branch,
        "item": item,
        "cust": _token(users["cust"], "Customer"),
        "cust2": _token(users["cust2"], "Customer"),
        "staff": _token(users["staff"], "KitchenStaff"),
        "admin": _token(users["admin"], "PlatformAdmin"),
    }


@pytest.fixture
def kitchen(monkeypatch) -> AsyncMock:
    """Records every message sent to the restaurant's live screens."""
    sent = AsyncMock()
    monkeypatch.setattr(ws_manager, "broadcast_to_branch", sent)
    return sent


async def place(
    client: AsyncClient, shop: dict, use_credit: bool = False, who: str = "cust"
) -> dict:
    res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(shop["branch"].id),
            "items": [{"menu_item_id": str(shop["item"].id), "quantity": 1}],
            "delivery_address_snapshot": {"branch_name": "Food Court"},
            "use_store_credit": use_credit,
        },
        headers=shop[who],
    )
    assert res.status_code == 201, res.text
    return res.json()


async def give_credit(db: AsyncSession, shop: dict, amount: float) -> None:
    await StoreCreditService(db).issue(
        customer_profile_id=shop["profile"].id,
        brand_id=shop["brand"].id,
        amount=amount,
        reason="GOODWILL",
    )
    await db.commit()


async def credit_balance(db: AsyncSession, shop: dict) -> float:
    return await StoreCreditService(db).get_balance(
        shop["profile"].id, shop["brand"].id
    )


async def age(db: AsyncSession, order_id: str, minutes: int) -> None:
    await db.execute(
        update(Order)
        .where(Order.id == uuid.UUID(order_id))
        .values(created_at=datetime.now(UTC) - timedelta(minutes=minutes))
    )
    await db.commit()


def placed_events(kitchen: AsyncMock) -> list[dict]:
    return [
        c.kwargs["message"]
        for c in kitchen.await_args_list
        if c.kwargs["message"].get("event") == "ORDER_PLACED"
    ]


async def intent_and_signature(client, shop, order_id: str, amount: float):
    intent = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order_id, "amount": amount},
        headers=shop["cust"],
    )
    assert intent.status_code == 201, intent.text
    rzp_order = str(intent.json()["razorpay_order_id"])
    rzp_pay = f"pay_{uuid.uuid4().hex[:10]}"
    secret = (RazorpayAdapter().key_secret or "").encode()
    sig = hmac.new(
        secret, f"{rzp_order}|{rzp_pay}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "order_id": order_id,
        "razorpay_order_id": rzp_order,
        "razorpay_payment_id": rzp_pay,
        "razorpay_signature": sig,
    }


# ----- A new order waits ---------------------------------------------------------------------


async def test_a_new_order_waits_for_payment_and_the_kitchen_hears_nothing(
    client, shop, kitchen
):
    order = await place(client, shop)
    assert order["status"] == "PENDING_PAYMENT"
    assert [log["new_status"] for log in order["status_logs"]] == ["PENDING_PAYMENT"]
    kitchen.assert_not_awaited()  # no beep, no new-order message


async def test_the_restaurant_cannot_see_an_unpaid_order(client, shop):
    order = await place(client, shop)
    branch = str(shop["branch"].id)
    for query in (
        f"?branch_id={branch}",
        f"?branch_id={branch}&status=PENDING_PAYMENT",
    ):
        listed = await client.get(f"/api/v1/orders{query}", headers=shop["staff"])
        assert listed.status_code == 200 and listed.json() == []
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["staff"])
    ).status_code == 404
    for status in ("ACCEPTED", "CANCELLED"):
        moved = await client.patch(
            f"/api/v1/orders/{order['id']}/status",
            json={"status": status},
            headers=shop["staff"],
        )
        assert moved.status_code == 404
    assert (
        await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=shop["staff"])
    ).status_code == 404


async def test_the_student_still_sees_their_unpaid_order(client, shop):
    order = await place(client, shop)
    mine = (await client.get("/api/v1/orders", headers=shop["cust"])).json()
    assert [(o["id"], o["status"]) for o in mine] == [(order["id"], "PENDING_PAYMENT")]


async def test_platform_staff_can_still_find_an_unpaid_order_to_help_a_student(
    client, shop
):
    order = await place(client, shop)
    found = await client.get(
        f"/api/v1/orders?branch_id={shop['branch'].id}&status=PENDING_PAYMENT",
        headers=shop["admin"],
    )
    assert [o["id"] for o in found.json()] == [order["id"]]
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["admin"])
    ).status_code == 200
    # ...but not mixed into the ordinary list
    plain = await client.get(
        f"/api/v1/orders?branch_id={shop['branch'].id}", headers=shop["admin"]
    )
    assert plain.json() == []


# ----- Paying makes it real ------------------------------------------------------------------


async def test_paying_places_the_order_and_tells_the_kitchen_exactly_once(
    client, shop, kitchen
):
    order = await place(client, shop)
    await pay_for_order(client, shop["cust"], order["id"])

    seen = await client.get(f"/api/v1/orders/{order['id']}", headers=shop["staff"])
    assert seen.status_code == 200 and seen.json()["status"] == "PLACED"
    listed = await client.get(
        f"/api/v1/orders?branch_id={shop['branch'].id}", headers=shop["staff"]
    )
    assert [o["id"] for o in listed.json()] == [order["id"]]
    assert [log["new_status"] for log in seen.json()["status_logs"]] == [
        "PENDING_PAYMENT",
        "PLACED",
    ]
    events = placed_events(kitchen)
    assert (
        len(events) == 1
        and events[0]["order_id"] == order["id"]
        and events[0]["status"] == "PLACED"
    )


async def test_confirming_the_same_payment_twice_is_harmless(
    client, db_session, shop, kitchen
):
    order = await place(client, shop)
    body = await intent_and_signature(client, shop, order["id"], PRICE)
    for _ in range(3):
        assert (
            await client.post(
                "/api/v1/payments/verify", json=body, headers=shop["cust"]
            )
        ).status_code == 200

    captured = await db_session.execute(
        select(func.count())
        .select_from(PaymentTransaction)
        .where(
            PaymentTransaction.transaction_type == "CAPTURED",
            PaymentTransaction.status == "SUCCESS",
        )
    )
    assert captured.scalar_one() == 1  # the money is counted once
    assert len(placed_events(kitchen)) == 1  # and the kitchen is told once


async def test_the_razorpay_webhook_places_the_order_too(client, shop, kitchen):
    order = await place(client, shop)
    intent = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust"],
    )
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_wh_{uuid.uuid4().hex[:8]}",
                    "order_id": intent.json()["razorpay_order_id"],
                    "amount": int(PRICE * 100),
                }
            }
        },
    }
    raw = json.dumps(payload)
    sig = hmac.new(
        (RazorpayAdapter().webhook_secret or "").encode(), raw.encode(), hashlib.sha256
    ).hexdigest()
    res = await client.post(
        "/api/v1/payments/webhook",
        content=raw,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["staff"])
    ).json()["status"] == "PLACED"
    assert len(placed_events(kitchen)) == 1


# ----- You can only pay what it costs, for your own order ------------------------------------


async def test_the_amount_has_to_be_what_the_order_costs(client, shop):
    order = await place(client, shop)
    for wrong in (1.0, 99.0, 100.5, 1000.0):
        res = await client.post(
            "/api/v1/payments/intent",
            json={"order_id": order["id"], "amount": wrong},
            headers=shop["cust"],
        )
        assert (
            res.status_code == 422
            and res.json()["error_code"] == "PAYMENT_AMOUNT_MISMATCH"
        ), wrong
    ok = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust"],
    )
    assert ok.status_code == 201


async def test_the_amount_takes_store_credit_into_account(client, db_session, shop):
    await give_credit(db_session, shop, 30)
    order = await place(client, shop, use_credit=True)
    assert order["store_credit_applied"] == 30 and order["status"] == "PENDING_PAYMENT"
    full = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust"],
    )
    assert full.status_code == 422  # they only owe 70 now
    ok = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": 70.0},
        headers=shop["cust"],
    )
    assert ok.status_code == 201


async def test_only_the_orders_own_customer_can_pay_for_it(client, shop):
    order = await place(client, shop)
    res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust2"],
    )
    assert (
        res.status_code == 403 and res.json()["error_code"] == "ORDER_ACCESS_FORBIDDEN"
    )
    missing = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": str(uuid.uuid4()), "amount": PRICE},
        headers=shop["cust"],
    )
    assert missing.status_code == 404


async def test_a_cancelled_order_cannot_be_paid_for(client, shop):
    order = await place(client, shop)
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=shop["cust"])
    res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust"],
    )
    assert res.status_code == 400 and res.json()["error_code"] == "ORDER_NOT_PAYABLE"
    assert "place it again" in res.json()["message"]


async def test_an_order_cannot_be_paid_for_twice(client, shop):
    order = await place(client, shop)
    await pay_for_order(client, shop["cust"], order["id"])
    res = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order["id"], "amount": PRICE},
        headers=shop["cust"],
    )
    assert res.status_code == 400
    assert res.json()["error_code"] in {"ORDER_ALREADY_PAID", "ORDER_NOT_PAYABLE"}


# ----- Abandoned orders and store credit -----------------------------------------------------


async def test_cancelling_an_unpaid_order_gives_the_credit_back_and_the_kitchen_hears_nothing(
    client, db_session, shop, kitchen
):
    await give_credit(db_session, shop, 60)
    order = await place(client, shop, use_credit=True)
    assert (
        await credit_balance(db_session, shop) == 0
    )  # spent when the order was created

    res = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=shop["cust"]
    )
    assert res.status_code == 200 and res.json()["status"] == "CANCELLED"
    assert await credit_balance(db_session, shop) == 60  # and returned
    kitchen.assert_not_awaited()


async def test_an_order_not_paid_in_time_is_cancelled_and_the_credit_returned(
    client, db_session, shop, kitchen
):
    await give_credit(db_session, shop, 60)
    abandoned = await place(client, shop, use_credit=True)
    fresh = await place(client, shop)
    await age(db_session, abandoned["id"], 31)
    await age(db_session, fresh["id"], 5)

    mine = {
        o["id"]: o["status"]
        for o in (await client.get("/api/v1/orders", headers=shop["cust"])).json()
    }

    assert mine[abandoned["id"]] == "CANCELLED"
    assert mine[fresh["id"]] == "PENDING_PAYMENT"  # still inside the payment window
    assert await credit_balance(db_session, shop) == 60
    kitchen.assert_not_awaited()
    # and it is not done twice
    await client.get("/api/v1/orders", headers=shop["cust"])
    assert await credit_balance(db_session, shop) == 60


async def test_an_order_that_was_actually_paid_is_placed_not_expired(
    client, db_session, shop, kitchen
):
    """The payment went through but the confirmation never reached us. It must not be cancelled."""
    order = await place(client, shop)
    payment = Payment(
        order_id=uuid.UUID(order["id"]),
        customer_profile_id=shop["profile"].id,
        amount=PRICE,
    )
    db_session.add(payment)
    await db_session.flush()
    db_session.add(
        PaymentTransaction(
            payment_id=payment.id,
            transaction_type="CAPTURED",
            amount=PRICE,
            status="SUCCESS",
        )
    )
    await db_session.commit()
    await age(db_session, order["id"], 45)

    mine = (await client.get("/api/v1/orders", headers=shop["cust"])).json()
    assert mine[0]["status"] == "PLACED"
    assert len(placed_events(kitchen)) == 1


async def test_a_payment_that_arrives_after_the_order_expired_becomes_store_credit(
    client, db_session, shop, kitchen
):
    order = await place(client, shop)
    body = await intent_and_signature(
        client, shop, order["id"], PRICE
    )  # they start paying...
    await age(db_session, order["id"], 31)
    await client.get(
        "/api/v1/orders", headers=shop["cust"]
    )  # ...but the order expires meanwhile
    assert await credit_balance(db_session, shop) == 0

    res = await client.post(
        "/api/v1/payments/verify", json=body, headers=shop["cust"]
    )  # ...and then it goes through

    assert res.status_code == 200
    assert await credit_balance(db_session, shop) == PRICE  # their money is not lost
    mine = (await client.get("/api/v1/orders", headers=shop["cust"])).json()
    assert mine[0]["status"] == "CANCELLED"  # the order is not resurrected
    assert placed_events(kitchen) == []  # the kitchen never hears of it
    await client.post(
        "/api/v1/payments/verify", json=body, headers=shop["cust"]
    )  # a retry
    assert await credit_balance(db_session, shop) == PRICE  # no double credit


async def test_paying_for_a_paid_order_then_cancelling_gives_credit_once(
    client, db_session, shop
):
    """A cancellation turns what was captured into store credit. Capturing twice must not double it."""
    order = await place(client, shop)
    body = await intent_and_signature(client, shop, order["id"], PRICE)
    for _ in range(2):
        await client.post("/api/v1/payments/verify", json=body, headers=shop["cust"])
    await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "CANCELLED"},
        headers=shop["staff"],
    )
    assert await credit_balance(db_session, shop) == PRICE


async def test_an_order_store_credit_fully_covers_goes_straight_to_the_kitchen(
    client, db_session, shop, kitchen
):
    """There is no payment to wait for, so it must not sit in 'waiting' forever."""
    await give_credit(db_session, shop, 100)
    order = await place(client, shop, use_credit=True)
    assert order["status"] == "PLACED" and order["store_credit_applied"] == 100
    assert [
        o["id"]
        for o in (
            await client.get(
                f"/api/v1/orders?branch_id={shop['branch'].id}", headers=shop["staff"]
            )
        ).json()
    ] == [order["id"]]
    assert len(placed_events(kitchen)) == 1


async def test_customers_orders_are_kept_separate(client, db_session, shop):
    mine = await place(client, shop)
    await age(db_session, mine["id"], 31)
    theirs = await place(client, shop, who="cust2")
    await age(db_session, theirs["id"], 31)
    await client.get(
        "/api/v1/orders", headers=shop["cust"]
    )  # only the first student opens their list
    statuses = {
        r.id: r.status
        for r in (await db_session.execute(select(Order))).scalars().all()
    }
    assert statuses[uuid.UUID(mine["id"])] == "CANCELLED"
    assert statuses[uuid.UUID(theirs["id"])] == "PENDING_PAYMENT"


# ----- Everything else that counts orders ----------------------------------------------------


async def test_the_admin_totals_ignore_orders_nobody_paid_for(client, db_session, shop):
    await place(client, shop)  # unpaid
    await place(client, shop)  # unpaid
    paid = await place(client, shop)
    await pay_for_order(client, shop["cust"], paid["id"])

    overview = await AdminRepository(db_session).get_analytics_overview()

    assert overview["total_orders"] == 1
    assert overview["gross_revenue"] == PRICE


async def test_whatsapp_and_payouts_only_ever_see_paid_orders(client, db_session, shop):
    order = await place(client, shop)
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=shop["cust"])
    assert (
        await db_session.execute(select(func.count()).select_from(Notification))
    ).scalar_one() == 0


# ----- An order that was cancelled before it was ever paid never reached the restaurant ------


async def test_an_order_cancelled_while_unpaid_never_appears_in_the_restaurants_history(
    client, shop, kitchen
):
    order = await place(client, shop)
    await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=shop["cust"]
    )  # the student gave up

    for query in ("", "&status=CANCELLED"):
        listed = await client.get(
            f"/api/v1/orders?branch_id={shop['branch'].id}{query}",
            headers=shop["staff"],
        )
        assert (
            listed.json() == []
        ), query  # not in "Done today", not in any cancelled count
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["staff"])
    ).status_code == 404
    mine = (await client.get("/api/v1/orders", headers=shop["cust"])).json()
    assert [(o["id"], o["status"]) for o in mine] == [
        (order["id"], "CANCELLED")
    ]  # the student keeps theirs
    kitchen.assert_not_awaited()


async def test_an_order_that_expired_while_unpaid_never_appears_in_the_restaurants_history(
    client, db_session, shop
):
    order = await place(client, shop)
    await age(db_session, order["id"], 45)
    await client.get("/api/v1/orders", headers=shop["cust"])  # expires it
    listed = await client.get(
        f"/api/v1/orders?branch_id={shop['branch'].id}", headers=shop["staff"]
    )
    assert listed.json() == []


async def test_an_order_cancelled_after_it_was_paid_stays_in_the_restaurants_history(
    client, shop
):
    """Only orders that never reached the restaurant are hidden: one they did receive still counts."""
    order = await place(client, shop)
    await pay_for_order(client, shop["cust"], order["id"])
    await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "CANCELLED"},
        headers=shop["staff"],
    )
    listed = await client.get(
        f"/api/v1/orders?branch_id={shop['branch'].id}", headers=shop["staff"]
    )
    assert [(o["id"], o["status"]) for o in listed.json()] == [
        (order["id"], "CANCELLED")
    ]
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["staff"])
    ).status_code == 200


async def test_platform_staff_still_see_orders_cancelled_while_unpaid(client, shop):
    order = await place(client, shop)
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=shop["cust"])
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=shop["admin"])
    ).status_code == 200


async def test_the_admin_totals_ignore_orders_cancelled_while_unpaid_too(
    client, db_session, shop
):
    gave_up = await place(client, shop)
    await client.post(f"/api/v1/orders/{gave_up['id']}/cancel", headers=shop["cust"])
    await place(client, shop)  # still waiting
    paid = await place(client, shop)
    await pay_for_order(client, shop["cust"], paid["id"])
    overview = await AdminRepository(db_session).get_analytics_overview()
    assert overview["total_orders"] == 1 and overview["gross_revenue"] == PRICE
