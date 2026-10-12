import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.garba.models import GarbaBooking
from app.garba.pricing import total_amount
from app.payment.razorpay_adapter import RazorpayAdapter


@pytest.fixture(autouse=True)
def _simulate_razorpay(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", True)


@pytest.fixture
async def garba_customer(db_session: AsyncSession):
    user = User(
        email="garba_cust@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    other = User(
        email="garba_other@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add_all([user, other])
    await db_session.flush()
    profile = CustomerProfile(
        user_id=user.id, full_name="Garba Customer", phone_number="9876543210"
    )
    other_profile = CustomerProfile(
        user_id=other.id, full_name="Other Customer", phone_number="9876543211"
    )
    db_session.add_all([profile, other_profile])
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role)}"
    }
    other_headers = {
        "Authorization": (
            f"Bearer {create_access_token(subject=str(other.id), role=other.role)}"
        )
    }
    return {"headers": headers, "other_headers": other_headers, "profile": profile}


def _people(count: int, start: int) -> list[dict[str, str]]:
    rows = []
    for offset in range(count):
        n = start + offset
        rows.append({"name": f"Guest {n:02d}", "phone": f"9{n:09d}"})
    return rows


def _sign(order_id: str, payment_id: str) -> str:
    secret = RazorpayAdapter().key_secret or ""
    msg = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


async def _book(
    client: AsyncClient,
    headers: dict,
    *,
    category: str,
    dates: str,
    quantity: int,
    start: int,
    extra: dict | None = None,
):
    people = quantity * 2 if category == "couple" else quantity
    body = {
        "category": category,
        "dates": dates,
        "quantity": quantity,
        "attendees": _people(people, start),
    }
    if extra:
        body.update(extra)
    return await client.post("/api/v1/events/garba/bookings", json=body, headers=headers)


@pytest.mark.parametrize(
    ("category", "dates", "quantity", "expected"),
    [
        ("men", "17", 1, 499),
        ("men", "18", 1, 499),
        ("women", "17", 2, 998),
        ("women", "both", 1, 799),
        ("men", "both", 3, 2397),
        ("couple", "17", 1, 799),
        ("couple", "18", 2, 1598),
        ("couple", "both", 1, 1399),
        ("couple", "both", 2, 2798),
    ],
)
def test_price_calculation(category, dates, quantity, expected):
    assert total_amount(category, dates, quantity) == expected


@pytest.mark.asyncio
async def test_booking_charges_server_price_and_hides_secret(
    client: AsyncClient, garba_customer: dict, monkeypatch
):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_public")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "super-secret-value")
    response = await _book(
        client,
        garba_customer["headers"],
        category="women",
        dates="both",
        quantity=2,
        start=100,
        extra={"amount": 1, "ticket_numbers": ["GN26-WN-HACK"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 1598
    assert data["currency"] == "INR"
    assert data["key_id"] == "rzp_test_public"
    assert data["is_simulated"] is True
    assert data["razorpay_order_id"].startswith("order_sim_")
    assert "super-secret-value" not in response.text
    assert "status" not in data

    mine = await client.get(
        "/api/v1/events/garba/bookings/me", headers=garba_customer["headers"]
    )
    assert mine.status_code == 200
    assert mine.json() == []


@pytest.mark.asyncio
async def test_availability_is_public_and_booking_requires_customer(
    client: AsyncClient, garba_customer: dict
):
    public = await client.get("/api/v1/events/garba/availability")
    assert public.status_code == 200
    body = public.json()
    assert body["name"] == "Saturdays Garba Night"
    assert body["venue"] == "The Hooks"
    assert body["dates"] == {"17": "2026-10-17", "18": "2026-10-18"}
    assert body["remaining"]["men"] == {"17": 35, "18": 35, "both": 35}
    assert body["remaining"]["women"]["17"] == 55
    assert body["remaining"]["couple"]["both"] == 30
    assert body["prices"]["couple"] == {"17": 799, "18": 799, "both": 1399}

    denied = await client.post(
        "/api/v1/events/garba/bookings",
        json={
            "category": "men",
            "dates": "17",
            "quantity": 1,
            "attendees": [{"name": "Amit Patel", "phone": "9876543210"}],
        },
    )
    assert denied.status_code == 401
    assert (
        await client.get("/api/v1/events/garba/bookings/me")
    ).status_code == 401


@pytest.mark.asyncio
async def test_attendee_rules(client: AsyncClient, garba_customer: dict):
    headers = garba_customer["headers"]
    short_name = await client.post(
        "/api/v1/events/garba/bookings",
        json={
            "category": "men",
            "dates": "17",
            "quantity": 1,
            "attendees": [{"name": " A ", "phone": "9876543210"}],
        },
        headers=headers,
    )
    assert short_name.status_code == 422

    bad_phone = await client.post(
        "/api/v1/events/garba/bookings",
        json={
            "category": "men",
            "dates": "17",
            "quantity": 1,
            "attendees": [{"name": "Amit Patel", "phone": "5876543210"}],
        },
        headers=headers,
    )
    assert bad_phone.status_code == 422

    one_person_couple = await client.post(
        "/api/v1/events/garba/bookings",
        json={
            "category": "couple",
            "dates": "18",
            "quantity": 1,
            "attendees": [{"name": "Amit Patel", "phone": "9876543210"}],
        },
        headers=headers,
    )
    assert one_person_couple.status_code == 422

    too_many = await _book(
        client, headers, category="men", dates="17", quantity=5, start=1
    )
    assert too_many.status_code == 422


@pytest.mark.asyncio
async def test_both_pass_takes_one_seat_on_each_date(
    client: AsyncClient, garba_customer: dict
):
    headers = garba_customer["headers"]
    created = await _book(
        client, headers, category="men", dates="both", quantity=2, start=200
    )
    assert created.status_code == 201
    assert created.json()["amount"] == 1598

    day = await _book(
        client, headers, category="men", dates="17", quantity=4, start=210
    )
    assert day.status_code == 201

    avail = (await client.get("/api/v1/events/garba/availability")).json()
    assert avail["remaining"]["men"] == {"17": 29, "18": 33, "both": 29}
    assert avail["remaining"]["women"]["17"] == 55
    assert avail["remaining"]["couple"]["17"] == 30


@pytest.mark.asyncio
async def test_both_pass_blocked_when_one_date_is_full(
    client: AsyncClient, garba_customer: dict
):
    headers = garba_customer["headers"]
    start = 300
    for quantity in (4, 4, 4, 4, 4, 4, 4, 4, 3):
        response = await _book(
            client,
            headers,
            category="men",
            dates="17",
            quantity=quantity,
            start=start,
        )
        assert response.status_code == 201, response.text
        start += quantity

    avail = (await client.get("/api/v1/events/garba/availability")).json()
    assert avail["remaining"]["men"]["17"] == 0
    assert avail["remaining"]["men"]["18"] == 35
    assert avail["remaining"]["men"]["both"] == 0
    assert avail["remaining"]["women"]["18"] == 55

    blocked = await _book(
        client, headers, category="men", dates="both", quantity=1, start=900
    )
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "SOLD_OUT"

    other_day = await _book(
        client, headers, category="men", dates="18", quantity=1, start=910
    )
    assert other_day.status_code == 201


@pytest.mark.asyncio
async def test_expired_hold_releases_capacity(
    client: AsyncClient, garba_customer: dict, db_session: AsyncSession
):
    headers = garba_customer["headers"]
    start = 1000
    first_id = None
    # 13 * 4 + 3 = 55, the women's cap for one date.
    for quantity in (4,) * 13 + (3,):
        response = await _book(
            client,
            headers,
            category="women",
            dates="18",
            quantity=quantity,
            start=start,
        )
        assert response.status_code == 201, response.text
        first_id = first_id or response.json()["booking_id"]
        start += quantity

    full = await _book(
        client, headers, category="women", dates="18", quantity=1, start=1200
    )
    assert full.status_code == 409

    old = datetime.now(timezone.utc) - timedelta(days=1)
    rows = (await db_session.execute(select(GarbaBooking))).scalars().all()
    for row in rows:
        row.created_at = old
    await db_session.commit()

    released = (await client.get("/api/v1/events/garba/availability")).json()
    assert released["remaining"]["women"] == {"17": 55, "18": 55, "both": 55}

    again = await _book(
        client, headers, category="women", dates="18", quantity=1, start=1300
    )
    assert again.status_code == 201

    payment_id = "pay_expired_hold"
    stored = await db_session.get(GarbaBooking, uuid.UUID(first_id))
    assert stored is not None
    expired = await client.post(
        f"/api/v1/events/garba/bookings/{first_id}/verify",
        json={
            "razorpay_order_id": stored.razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": _sign(stored.razorpay_order_id, payment_id),
        },
        headers=headers,
    )
    assert expired.status_code == 400
    assert expired.json()["error_code"] == "HOLD_EXPIRED"
    await db_session.refresh(stored)
    assert stored.status == "EXPIRED"
    assert stored.ticket_numbers is None


@pytest.mark.asyncio
async def test_invalid_signature_does_not_issue_tickets(
    client: AsyncClient, garba_customer: dict, db_session: AsyncSession
):
    headers = garba_customer["headers"]
    created = await _book(
        client, headers, category="men", dates="17", quantity=1, start=1400
    )
    assert created.status_code == 201
    booking_id = created.json()["booking_id"]
    order_id = created.json()["razorpay_order_id"]

    bad = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_bad",
            "razorpay_signature": "not-a-real-signature",
            "ticket_numbers": ["GN26-MN-HACK"],
            "amount": 1,
        },
        headers=headers,
    )
    assert bad.status_code == 400
    assert bad.json()["error_code"] == "INVALID_PAYMENT_SIGNATURE"

    mismatch = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json={
            "razorpay_order_id": "order_other",
            "razorpay_payment_id": "pay_bad",
            "razorpay_signature": _sign("order_other", "pay_bad"),
        },
        headers=headers,
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error_code"] == "RAZORPAY_ORDER_MISMATCH"

    stored = await db_session.get(GarbaBooking, uuid.UUID(booking_id))
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.status == "PENDING"
    assert stored.ticket_numbers is None
    assert stored.razorpay_payment_id is None
    assert int(stored.amount) == 499

    avail = (await client.get("/api/v1/events/garba/availability")).json()
    assert avail["remaining"]["men"]["17"] == 34
    mine = await client.get("/api/v1/events/garba/bookings/me", headers=headers)
    assert mine.json() == []


@pytest.mark.asyncio
async def test_verify_is_idempotent_and_rejects_a_second_payment(
    client: AsyncClient, garba_customer: dict
):
    headers = garba_customer["headers"]
    created = await _book(
        client, headers, category="couple", dates="both", quantity=1, start=1500
    )
    assert created.status_code == 201
    assert created.json()["amount"] == 1399
    booking_id = created.json()["booking_id"]
    order_id = created.json()["razorpay_order_id"]
    payment_id = "pay_couple_once"
    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": _sign(order_id, payment_id),
        "ticket_numbers": ["GN26-CP-HACK"],
        "amount": 1,
    }

    first = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 200
    paid = first.json()
    assert paid["status"] == "PAID"
    assert paid["ticket_numbers"] == ["GN26-CP-0001", "GN26-CP-0002"]
    assert "GN26-CP-HACK" not in paid["ticket_numbers"]
    assert len(paid["attendees"]) == 2
    assert paid["amount"] == 1399

    second = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json=payload,
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["ticket_numbers"] == paid["ticket_numbers"]

    other_payment = "pay_couple_twice"
    replay = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": other_payment,
            "razorpay_signature": _sign(order_id, other_payment),
        },
        headers=headers,
    )
    assert replay.status_code == 409
    assert replay.json()["error_code"] == "BOOKING_ALREADY_PAID"

    stranger = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json=payload,
        headers=garba_customer["other_headers"],
    )
    assert stranger.status_code == 404

    mine = await client.get("/api/v1/events/garba/bookings/me", headers=headers)
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["ticket_numbers"] == ["GN26-CP-0001", "GN26-CP-0002"]
    other_mine = await client.get(
        "/api/v1/events/garba/bookings/me", headers=garba_customer["other_headers"]
    )
    assert other_mine.json() == []

    nxt = await _book(
        client, headers, category="couple", dates="17", quantity=1, start=1600
    )
    nxt_id = nxt.json()["booking_id"]
    nxt_order = nxt.json()["razorpay_order_id"]
    nxt_pay = "pay_couple_next"
    issued = await client.post(
        f"/api/v1/events/garba/bookings/{nxt_id}/verify",
        json={
            "razorpay_order_id": nxt_order,
            "razorpay_payment_id": nxt_pay,
            "razorpay_signature": _sign(nxt_order, nxt_pay),
        },
        headers=headers,
    )
    assert issued.status_code == 200
    assert issued.json()["ticket_numbers"] == ["GN26-CP-0003", "GN26-CP-0004"]
    assert len(issued.json()["passes"]) == 2
    assert issued.json()["passes"][0]["qr_token"]


@pytest.mark.asyncio
async def test_admin_capacity_and_entry_scan(
    client: AsyncClient, garba_customer: dict, db_session: AsyncSession
):
    admin = User(
        email="garba_admin@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Admin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    admin_headers = {
        "Authorization": (
            f"Bearer {create_access_token(subject=str(admin.id), role=admin.role)}"
        )
    }
    denied = await client.patch(
        "/api/v1/events/garba/admin/inventory",
        json={"category": "men", "event_date": "17", "capacity": 2},
        headers=garba_customer["headers"],
    )
    assert denied.status_code == 403

    updated = await client.patch(
        "/api/v1/events/garba/admin/inventory",
        json={"category": "men", "event_date": "17", "capacity": 2},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 2
    assert updated.json()["sold"] == 0

    avail = (await client.get("/api/v1/events/garba/availability")).json()
    assert avail["remaining"]["men"]["17"] == 2
    assert avail["remaining"]["men"]["18"] == 35
    assert avail["capacity"]["men"]["17"] == 2

    created = await _book(
        client,
        garba_customer["headers"],
        category="men",
        dates="17",
        quantity=2,
        start=2000,
    )
    assert created.status_code == 201
    booking_id = created.json()["booking_id"]
    order_id = created.json()["razorpay_order_id"]
    payment_id = "pay_admin_scan"
    paid = await client.post(
        f"/api/v1/events/garba/bookings/{booking_id}/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": _sign(order_id, payment_id),
        },
        headers=garba_customer["headers"],
    )
    assert paid.status_code == 200
    token = paid.json()["passes"][0]["qr_token"]
    after = (await client.get("/api/v1/events/garba/availability")).json()
    assert after["remaining"]["men"]["17"] == 0

    first = await client.post(
        "/api/v1/events/garba/admin/scan",
        json={"code": token},
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert first.json()["admitted"] is True
    assert first.json()["already_entered"] is False

    second = await client.post(
        "/api/v1/events/garba/admin/scan",
        json={"code": token},
        headers=admin_headers,
    )
    assert second.status_code == 200
    assert second.json()["admitted"] is False
    assert second.json()["already_entered"] is True

    unknown = await client.post(
        "/api/v1/events/garba/admin/scan",
        json={"code": "not-a-ticket"},
        headers=admin_headers,
    )
    assert unknown.status_code == 404
