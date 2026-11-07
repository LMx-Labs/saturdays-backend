"""WhatsApp order updates: when a message is sent, when it must not be, and that it can never
break an order. Drives the real payment and order endpoints, with a mock WhatsApp."""

import asyncio
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.main import app as fastapi_app
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.notification.models import Notification
from app.notification.order_code import order_code
from app.notification.whatsapp import (
    CloudApiWhatsAppProvider,
    MockWhatsAppProvider,
    TemplateMessage,
    WhatsAppProviderInterface,
    WhatsAppSendError,
    build_whatsapp_provider,
    clean_param,
)
from app.notification.whatsapp_service import (
    ORDER_CANCELLED,
    ORDER_CONFIRMED,
    ORDER_READY,
    WhatsAppNotifier,
    build_params,
    get_whatsapp_notifier,
    pickup_phrase,
    render_preview,
)
from app.notification.whatsapp_webhook import STOP_WORDS
from app.payment.razorpay_adapter import RazorpayAdapter

PHONE = "919876543210"


# ----- Fixtures --------------------------------------------------------------------------------


@pytest.fixture
async def ctx(db_session: AsyncSession) -> dict:
    cust_user = User(
        email="wa_cust@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    staff_user = User(
        email="wa_staff@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="KitchenStaff",
        is_active=True,
    )
    db_session.add_all([cust_user, staff_user])
    await db_session.flush()
    profile = CustomerProfile(
        user_id=cust_user.id,
        full_name="Asha Kumar",
        phone_number="98765 43210",
        whatsapp_opt_in=True,
        whatsapp_phone=PHONE,
    )
    merchant = Merchant(
        owner_user_id=staff_user.id,
        business_name="WA Merchant",
        legal_entity_name="WA Merchant LLC",
        fssai_license_number="11223344556677",
    )
    db_session.add_all([profile, merchant])
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="WA Brand")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Food Court", address_text="Campus Gate 1")
    db_session.add(branch)
    await db_session.flush()
    menu = Menu(branch_id=branch.id, name="Main")
    db_session.add(menu)
    await db_session.flush()
    category = MenuCategory(menu_id=menu.id, name="Meals")
    db_session.add(category)
    await db_session.flush()
    item = MenuItem(category_id=category.id, name="Chicken Biryani", base_price=80.00)
    item2 = MenuItem(category_id=category.id, name="Dal Fry", base_price=30.00)
    db_session.add_all([item, item2])
    await db_session.commit()
    cust_token = create_access_token(subject=str(cust_user.id), role="Customer")
    staff_token = create_access_token(subject=str(staff_user.id), role="KitchenStaff")
    return {
        "cust_user": cust_user,
        "profile": profile,
        "branch": branch,
        "item": item,
        "item2": item2,
        "cust": {"Authorization": f"Bearer {cust_token}"},
        "staff": {"Authorization": f"Bearer {staff_token}"},
    }


@pytest.fixture
async def wa(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> SimpleNamespace:
    """WhatsApp switched on, with a mock provider in place of Meta."""
    provider = MockWhatsAppProvider()
    notifier = WhatsAppNotifier(db_session, provider=provider)
    fastapi_app.dependency_overrides[get_whatsapp_notifier] = lambda: notifier
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_TEST_ALLOWLIST", "")
    return SimpleNamespace(provider=provider, notifier=notifier)


async def place(client: AsyncClient, ctx: dict, snapshot: dict | None = None) -> str:
    res = await client.post(
        "/api/v1/orders",
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [
                {"menu_item_id": str(ctx["item"].id), "quantity": 2},
                {"menu_item_id": str(ctx["item2"].id), "quantity": 1},
            ],
            "delivery_address_snapshot": snapshot or {"branch_name": "Food Court"},
        },
        headers=ctx["cust"],
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def pay(client: AsyncClient, ctx: dict, order_id: str) -> None:
    intent = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order_id, "amount": 190.0},
        headers=ctx["cust"],
    )
    assert intent.status_code == 201, intent.text
    rzp_order = str(intent.json()["razorpay_order_id"])
    rzp_pay = f"pay_{uuid.uuid4().hex[:10]}"
    secret = (RazorpayAdapter().key_secret or "").encode()
    sig = hmac.new(
        secret, f"{rzp_order}|{rzp_pay}".encode(), hashlib.sha256
    ).hexdigest()
    body = {
        "order_id": order_id,
        "razorpay_order_id": rzp_order,
        "razorpay_payment_id": rzp_pay,
        "razorpay_signature": sig,
    }
    ctx.setdefault("last_verify", {})[order_id] = body  # so it can be repeated
    res = await client.post("/api/v1/payments/verify", json=body, headers=ctx["cust"])
    assert res.status_code == 200, res.text


async def confirm_payment_again(client: AsyncClient, ctx: dict, order_id: str) -> None:
    """Confirm the very same payment a second time (a retry, or the webhook arriving too)."""
    res = await client.post(
        "/api/v1/payments/verify",
        json=ctx["last_verify"][order_id],
        headers=ctx["cust"],
    )
    assert res.status_code == 200, res.text


async def move(
    client: AsyncClient, ctx: dict, order_id: str, *statuses: str, headers=None
):
    res = None
    for status in statuses:
        res = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": status},
            headers=headers or ctx["staff"],
        )
        assert res.status_code == 200, res.text
    return res


async def log(db: AsyncSession) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.channel == "WHATSAPP")
        .order_by(Notification.created_at)
    )
    return list(result.scalars().all())


# ----- The message wording ---------------------------------------------------------------------


def test_the_order_code_matches_the_frontend_exactly():
    # Reference values produced by running the real TypeScript orderCode() on these ids.
    vectors = [
        ("01a1b4a5-c6d2-7e11-b0f3-9a8c1d2e3f40", "5H8A"),
        ("01a1b4a5-c6d2-7e11-b0f3-0a1b2c3d4e51", "Q4DE"),
        ("01a1b4a5-c6d2-7e11-b0f3-77aa88bb99cc", "YZMC"),
        ("0194c7e2-3a10-7b3a-9d44-5f4e3d2c1b0a", "B2SN"),
        ("ffffffff-ffff-4fff-bfff-ffffffffffff", "NYT5"),
        ("00000000-0000-0000-0000-000000000000", "2222"),
        ("01a1b4a5-c6d2-7e11-b0f3-000000000001", "2223"),
    ]
    for order_id, expected in vectors:
        assert order_code(order_id) == expected
    assert order_code(uuid.UUID(vectors[0][0])) == "5H8A"
    assert order_code("") == "----"


def test_pickup_is_described_in_plain_words():
    now = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)  # 1:30 PM at the stall
    assert pickup_phrase("2026-11-10T14:05:00+05:30", now) == "today at 2:05 PM"
    assert pickup_phrase("2026-11-11T09:00:00+05:30", now) == "tomorrow at 9:00 AM"
    assert pickup_phrase("2026-11-13T18:30:00+05:30", now) == "Fri 13 Nov at 6:30 PM"
    assert (
        pickup_phrase("2026-11-10T08:45:00+00:00", now) == "today at 2:15 PM"
    )  # converted
    for nothing in (None, "", "not a date", 42):
        assert pickup_phrase(nothing, now) == "as soon as it's ready"


def test_each_message_has_the_right_details():
    now = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    common = {
        "customer_name": "Asha Kumar",
        "code": "K7M2",
        "branch_name": "Food Court",
        "now": now,
    }
    confirmed = build_params(
        ORDER_CONFIRMED, pickup_at="2026-11-10T14:05:00+05:30", total=190, **common
    )
    assert confirmed == ["Asha", "K7M2", "Food Court", "today at 2:05 PM", "190"]
    assert (
        build_params(ORDER_CONFIRMED, pickup_at=None, total=190.5, **common)[4]
        == "190.50"
    )
    assert build_params(ORDER_READY, pickup_at=None, total=0, **common) == [
        "K7M2",
        "Food Court",
    ]
    assert build_params(ORDER_CANCELLED, pickup_at=None, total=0, **common) == [
        "Asha",
        "Food Court",
        "K7M2",
    ]
    assert (
        build_params(
            ORDER_READY, pickup_at=None, total=0, **{**common, "customer_name": ""}
        )[0]
        == "K7M2"
    )
    with pytest.raises(ValueError):
        build_params("nonsense", pickup_at=None, total=0, **common)


def test_the_log_shows_what_the_customer_was_sent():
    text = render_preview(
        ORDER_CONFIRMED, ["Asha", "K7M2", "Food Court", "today at 2:05 PM", "190"]
    )
    assert "Hi Asha, your Saturdays order K7M2 at Food Court is confirmed" in text
    assert "Pickup: today at 2:05 PM" in text and "Total: ₹190" in text
    assert "{{" not in text


def test_parameters_are_made_safe_for_whatsapp():
    assert clean_param("line one\nline two\ttabbed") == "line one line two tabbed"
    assert clean_param("a      b") == "a   b"
    assert (
        clean_param("") == "-"
        and clean_param(None) == "-"
        and clean_param("   ") == "-"
    )
    assert len(clean_param("x" * 5000)) == 1000


# ----- Talking to Meta -------------------------------------------------------------------------


def _cloud(handler, **kw) -> CloudApiWhatsAppProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CloudApiWhatsAppProvider(
        phone_number_id="12345", access_token="TOKEN123", client=client, **kw
    )


async def test_the_cloud_provider_sends_what_meta_expects():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.ABC"}]})

    message = TemplateMessage(PHONE, "order_ready", "en", ["K7M2", "Food Court"])
    assert await _cloud(handler).send_template(message) == "wamid.ABC"
    assert seen["url"] == "https://graph.facebook.com/v21.0/12345/messages"
    assert seen["auth"] == "Bearer TOKEN123"
    assert seen["body"] == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": PHONE,
        "type": "template",
        "template": {
            "name": "order_ready",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "K7M2"},
                        {"type": "text", "text": "Food Court"},
                    ],
                }
            ],
        },
    }


async def test_a_rejected_message_says_why_and_is_not_retried():
    def handler(request):
        return httpx.Response(
            400, json={"error": {"code": 131026, "message": "Message undeliverable"}}
        )

    with pytest.raises(WhatsAppSendError) as caught:
        await _cloud(handler).send_template(
            TemplateMessage(PHONE, "order_ready", "en", ["a", "b"])
        )
    assert "131026" in str(caught.value) and "Message undeliverable" in str(
        caught.value
    )
    assert caught.value.retryable is False and caught.value.code == "131026"


@pytest.mark.parametrize("status", [500, 502, 503, 429])
async def test_a_server_problem_or_rate_limit_is_worth_retrying(status):
    with pytest.raises(WhatsAppSendError) as caught:
        await _cloud(lambda r: httpx.Response(status, json={})).send_template(
            TemplateMessage(PHONE, "t", "en")
        )
    assert caught.value.retryable is True


async def test_a_timeout_and_a_dropped_connection_are_reported_not_raised_raw():
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    def down(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(WhatsAppSendError, match="timed out"):
        await _cloud(slow).send_template(TemplateMessage(PHONE, "t", "en"))
    with pytest.raises(WhatsAppSendError, match="Could not reach"):
        await _cloud(down).send_template(TemplateMessage(PHONE, "t", "en"))


async def test_a_reply_without_a_message_id_is_an_error():
    with pytest.raises(WhatsAppSendError, match="no message id"):
        await _cloud(
            lambda r: httpx.Response(200, json={"messages": []})
        ).send_template(TemplateMessage(PHONE, "t", "en"))
    with pytest.raises(WhatsAppSendError):
        await _cloud(lambda r: httpx.Response(200, text="not json")).send_template(
            TemplateMessage(PHONE, "t", "en")
        )


async def test_the_token_never_appears_in_an_error():
    def handler(request):
        return httpx.Response(
            401, json={"error": {"code": 190, "message": "Invalid OAuth access token"}}
        )

    with pytest.raises(WhatsAppSendError) as caught:
        await _cloud(handler).send_template(TemplateMessage(PHONE, "t", "en"))
    assert "TOKEN123" not in str(caught.value)


def test_the_provider_is_chosen_from_the_settings(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "mock")
    assert isinstance(build_whatsapp_provider(settings), MockWhatsAppProvider)
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "cloud")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    assert build_whatsapp_provider(settings) is None  # half set up: refuse, don't crash
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "abc")
    assert isinstance(build_whatsapp_provider(settings), CloudApiWhatsAppProvider)
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "carrier-pigeon")
    assert build_whatsapp_provider(settings) is None


# ----- When a message is sent ------------------------------------------------------------------


async def test_paying_confirms_the_order_on_whatsapp(client, db_session, ctx, wa):
    soon = (
        (datetime.now(UTC) + timedelta(minutes=30))
        .astimezone()
        .strftime("%Y-%m-%dT%H:%M:00+00:00")
    )
    order_id = await place(
        client, ctx, {"branch_name": "Food Court", "pickup_at": soon}
    )
    assert wa.provider.sent == []  # created, but not paid yet: nothing

    await pay(client, ctx, order_id)

    assert len(wa.provider.sent) == 1
    message = wa.provider.sent[0]
    assert (
        message.to == PHONE
        and message.template == "order_confirmed"
        and message.language == "en"
    )
    name, code, stall, pickup, total = message.body_params
    assert (name, code, stall, total) == (
        "Asha",
        order_code(order_id),
        "Food Court",
        "190",
    )
    assert re.fullmatch(r"(today|tomorrow) at \d{1,2}:\d{2} (AM|PM)", pickup), pickup

    (row,) = await log(db_session)
    assert (row.status, row.event, str(row.order_id)) == (
        "SENT",
        "order_confirmed",
        order_id,
    )
    assert row.recipient == PHONE and row.vendor_message_id.startswith("mock_wamid_")
    assert order_code(order_id) in row.body


async def test_the_kitchen_marking_it_ready_tells_the_customer(
    client, db_session, ctx, wa
):
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "ACCEPTED", "PREPARING")
    assert [m.template for m in wa.provider.sent] == [
        "order_confirmed"
    ]  # cooking sends nothing

    await move(client, ctx, order_id, "READY")

    assert [m.template for m in wa.provider.sent] == ["order_confirmed", "order_ready"]
    assert wa.provider.sent[1].body_params == [order_code(order_id), "Food Court"]
    assert [r.event for r in await log(db_session)] == [
        "order_confirmed",
        "order_ready",
    ]
    await move(client, ctx, order_id, "COMPLETED")
    assert len(wa.provider.sent) == 2  # collecting it sends nothing more


async def test_a_restaurant_cancelling_tells_the_customer_about_their_credit(
    client, db_session, ctx, wa
):
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "CANCELLED")  # by the kitchen
    assert [m.template for m in wa.provider.sent] == [
        "order_confirmed",
        "order_cancelled",
    ]
    assert wa.provider.sent[1].body_params == [
        "Asha",
        "Food Court",
        order_code(order_id),
    ]
    assert "store credit" in (await log(db_session))[1].body


async def test_a_customer_cancelling_their_own_order_is_not_told_what_they_just_did(
    client, ctx, wa
):
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "CANCELLED", headers=ctx["cust"])
    assert [m.template for m in wa.provider.sent] == ["order_confirmed"]


async def test_an_unpaid_order_never_produces_a_message(client, db_session, ctx, wa):
    """Orders exist before payment. An abandoned checkout is invisible to the kitchen, so it can
    never be cooked or turned away; and the customer is never messaged about it, even when it is
    cancelled (by themselves, or by the platform when it expires)."""
    order_id = await place(client, ctx)
    staff_try = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "ACCEPTED"},
        headers=ctx["staff"],
    )
    assert staff_try.status_code == 404  # the kitchen cannot even find it
    other = await place(client, ctx)
    await move(
        client, ctx, other, "CANCELLED", headers=ctx["cust"]
    )  # the student cancels it
    assert wa.provider.sent == [] and await log(db_session) == []


async def test_the_same_message_is_never_sent_twice(client, db_session, ctx, wa):
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await confirm_payment_again(client, ctx, order_id)  # a retry, or the webhook too
    assert await wa.notifier.notify(uuid.UUID(order_id), ORDER_CONFIRMED) is False
    assert len(wa.provider.sent) == 1 and len(await log(db_session)) == 1


# ----- When a message must NOT be sent ---------------------------------------------------------


async def test_no_message_without_the_customers_consent(client, db_session, ctx, wa):
    ctx["profile"].whatsapp_opt_in = False
    await db_session.commit()
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "ACCEPTED", "PREPARING", "READY")
    assert wa.provider.sent == [] and await log(db_session) == []


async def test_no_message_without_a_number_to_send_to(client, db_session, ctx, wa):
    ctx["profile"].whatsapp_phone = None
    await db_session.commit()
    await pay(client, ctx, await place(client, ctx))
    assert wa.provider.sent == []


async def test_nothing_is_sent_while_whatsapp_is_switched_off(
    client, db_session, ctx, wa, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", False)
    await pay(client, ctx, await place(client, ctx))
    assert wa.provider.sent == [] and await log(db_session) == []


async def test_a_message_with_no_template_name_is_switched_off(
    client, db_session, ctx, wa, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_TEMPLATE_ORDER_READY", "")
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "ACCEPTED", "PREPARING", "READY")
    assert [m.template for m in wa.provider.sent] == ["order_confirmed"]


async def test_the_message_goes_to_the_whatsapp_number_not_the_typed_phone(
    client, db_session, ctx, wa
):
    ctx["profile"].phone_number = "11111 11111"
    ctx["profile"].whatsapp_phone = "919000011111"
    await db_session.commit()
    await pay(client, ctx, await place(client, ctx))
    assert wa.provider.sent[0].to == "919000011111"


async def test_while_testing_only_allow_listed_numbers_are_messaged(
    client, db_session, ctx, wa, monkeypatch
):
    monkeypatch.setattr(
        settings, "WHATSAPP_TEST_ALLOWLIST", "+91 90000 00000, 918888888888"
    )
    await pay(client, ctx, await place(client, ctx))
    assert (
        wa.provider.sent == []
    )  # a real customer's number is not on the list: protected
    monkeypatch.setattr(settings, "WHATSAPP_TEST_ALLOWLIST", f"+{PHONE}")
    await pay(client, ctx, await place(client, ctx))
    assert len(wa.provider.sent) == 1


# ----- It can never break an order -------------------------------------------------------------


async def test_a_failing_whatsapp_does_not_stop_the_payment_and_is_logged(
    client, db_session, ctx, wa
):
    wa.provider.fail_with = WhatsAppSendError("131026: Message undeliverable")
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)  # still succeeds (pay() asserts a 200)
    (row,) = await log(db_session)
    assert row.status == "FAILED" and "131026" in row.error
    await move(
        client, ctx, order_id, "ACCEPTED", "PREPARING", "READY"
    )  # and the kitchen carries on


async def test_a_crashing_provider_does_not_stop_the_order(client, db_session, ctx, wa):
    wa.provider.fail_with = RuntimeError("boom")
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "ACCEPTED", "PREPARING", "READY")
    assert {r.status for r in await log(db_session)} == {"FAILED"}


async def test_a_hanging_whatsapp_is_abandoned_quickly(
    client, db_session, ctx, monkeypatch
):
    class Hanging(WhatsAppProviderInterface):
        async def send_template(self, message):
            await asyncio.sleep(30)
            return "never"

    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_TIMEOUT_SECONDS", 0.1)
    notifier = WhatsAppNotifier(db_session, provider=Hanging())
    fastapi_app.dependency_overrides[get_whatsapp_notifier] = lambda: notifier
    order_id = await place(client, ctx)
    started = time.monotonic()
    await pay(client, ctx, order_id)
    assert time.monotonic() - started < 3  # not 30 seconds
    (row,) = await log(db_session)
    assert row.status == "FAILED" and "timed out" in row.error


async def test_a_half_configured_whatsapp_is_ignored_not_fatal(
    client, db_session, ctx, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "cloud")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    notifier = WhatsAppNotifier(
        db_session
    )  # no provider given: built from the (incomplete) settings
    fastapi_app.dependency_overrides[get_whatsapp_notifier] = lambda: notifier
    await pay(client, ctx, await place(client, ctx))
    assert await log(db_session) == []


async def test_orders_work_exactly_as_before_when_whatsapp_was_never_set_up(
    client, db_session, ctx
):
    order_id = await place(client, ctx)
    await pay(client, ctx, order_id)
    await move(client, ctx, order_id, "ACCEPTED", "PREPARING", "READY", "COMPLETED")
    assert await log(db_session) == []


# ----- What WhatsApp tells us back -------------------------------------------------------------

SECRET = "app-secret-for-tests"


def _sign(body: bytes, secret: str = SECRET) -> dict:
    return {
        "X-Hub-Signature-256": "sha256="
        + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        "Content-Type": "application/json",
    }


async def _post(client, payload: dict, *, signed: bool = True, secret: str = SECRET):
    body = json.dumps(payload).encode()
    return await client.post(
        "/api/v1/notifications/whatsapp/webhook",
        content=body,
        headers=_sign(body, secret) if signed else {"Content-Type": "application/json"},
    )


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", SECRET)
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "my-verify-token")


def _status_payload(message_id: str, status: str, **extra) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": message_id,
                                    "status": status,
                                    "timestamp": "1789000000",
                                    **extra,
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


async def _sent_record(db_session, ctx, message_id="wamid.TEST1") -> Notification:
    row = Notification(
        user_id=ctx["cust_user"].id,
        channel="WHATSAPP",
        recipient=PHONE,
        subject="order_ready",
        body="x",
        status="SENT",
        vendor_message_id=message_id,
        event="order_ready",
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def test_whatsapp_can_register_the_webhook(client, secret):
    ok = await client.get(
        "/api/v1/notifications/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my-verify-token",
            "hub.challenge": "1158201444",
        },
    )
    assert ok.status_code == 200 and ok.text == "1158201444"
    for params in (
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
        {
            "hub.mode": "unsubscribe",
            "hub.verify_token": "my-verify-token",
            "hub.challenge": "1",
        },
        {"hub.mode": "subscribe", "hub.verify_token": "my-verify-token"},
    ):
        assert (
            await client.get("/api/v1/notifications/whatsapp/webhook", params=params)
        ).status_code == 403


async def test_the_webhook_cannot_be_registered_before_a_verify_token_is_set(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "")
    res = await client.get(
        "/api/v1/notifications/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"},
    )
    assert res.status_code == 403


async def test_only_properly_signed_reports_are_accepted(client, secret):
    payload = _status_payload("wamid.X", "delivered")
    assert (await _post(client, payload, signed=False)).status_code == 403
    assert (await _post(client, payload, secret="the-wrong-secret")).status_code == 403
    assert (await _post(client, payload)).status_code == 200
    bad = b"not json"
    assert (
        await client.post(
            "/api/v1/notifications/whatsapp/webhook", content=bad, headers=_sign(bad)
        )
    ).status_code == 400
    arr = b"[1]"
    assert (
        await client.post(
            "/api/v1/notifications/whatsapp/webhook", content=arr, headers=_sign(arr)
        )
    ).status_code == 400


async def test_the_webhook_refuses_everything_until_an_app_secret_is_set(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", "")
    body = b"{}"
    for headers in (_sign(body, ""), _sign(body, SECRET), {}):
        assert (
            await client.post(
                "/api/v1/notifications/whatsapp/webhook", content=body, headers=headers
            )
        ).status_code == 403


async def test_delivery_reports_update_the_message_log(client, db_session, ctx, secret):
    row = await _sent_record(db_session, ctx)
    await _post(client, _status_payload("wamid.TEST1", "delivered"))
    await db_session.refresh(row)
    assert row.status == "DELIVERED" and row.delivered_at is not None
    await _post(client, _status_payload("wamid.TEST1", "read"))
    await db_session.refresh(row)
    assert row.status == "READ" and row.read_at is not None


async def test_late_or_out_of_order_reports_never_move_a_message_backwards(
    client, db_session, ctx, secret
):
    row = await _sent_record(db_session, ctx)
    await _post(client, _status_payload("wamid.TEST1", "read"))
    await _post(client, _status_payload("wamid.TEST1", "delivered"))
    await _post(client, _status_payload("wamid.TEST1", "sent"))
    await _post(
        client,
        _status_payload(
            "wamid.TEST1", "failed", errors=[{"code": 131026, "title": "late"}]
        ),
    )
    await db_session.refresh(row)
    assert row.status == "READ" and row.error is None


async def test_a_failed_delivery_is_recorded_with_the_reason(
    client, db_session, ctx, secret
):
    row = await _sent_record(db_session, ctx)
    await _post(
        client,
        _status_payload(
            "wamid.TEST1",
            "failed",
            errors=[{"code": 131026, "title": "Message undeliverable"}],
        ),
    )
    await db_session.refresh(row)
    assert row.status == "FAILED" and row.error == "131026: Message undeliverable"


async def test_reports_about_unknown_messages_are_ignored(client, secret):
    res = await _post(client, _status_payload("wamid.UNKNOWN", "delivered"))
    assert res.status_code == 200 and res.json()["updated"] == 0


def _inbound(sender: str, text: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": sender, "type": "text", "text": {"body": text}}
                            ]
                        }
                    }
                ]
            }
        ]
    }


@pytest.mark.parametrize(
    "reply", ["STOP", "stop", "Stop.", "  Stop all! ", "UNSUBSCRIBE", "opt out"]
)
async def test_a_customer_replying_stop_is_switched_off(
    client, db_session, ctx, secret, reply
):
    res = await _post(client, _inbound(PHONE, reply))
    assert res.json()["opted_out"] == 1
    await db_session.refresh(ctx["profile"])
    assert (
        ctx["profile"].whatsapp_opt_in is False
        and ctx["profile"].whatsapp_phone is None
    )


@pytest.mark.parametrize(
    "reply", ["thanks!", "cancel my order", "where is my food", "stopwatch"]
)
async def test_ordinary_replies_do_not_switch_anyone_off(
    client, db_session, ctx, secret, reply
):
    await _post(client, _inbound(PHONE, reply))
    await db_session.refresh(ctx["profile"])
    assert ctx["profile"].whatsapp_opt_in is True


async def test_stop_only_affects_the_person_who_sent_it(
    client, db_session, ctx, secret
):
    await _post(client, _inbound("919111122223", "STOP"))
    await db_session.refresh(ctx["profile"])
    assert ctx["profile"].whatsapp_opt_in is True


async def test_stopped_customers_get_no_more_messages(
    client, db_session, ctx, wa, secret
):
    await _post(client, _inbound(PHONE, "STOP"))
    await pay(client, ctx, await place(client, ctx))
    assert wa.provider.sent == []


def test_the_stop_words_do_not_include_ones_people_use_for_other_things():
    assert "cancel" not in STOP_WORDS and "stop" in STOP_WORDS


# ----- Can the app tell whether WhatsApp is live? ---------------------------------------------


async def test_the_app_is_told_whatsapp_is_off_until_it_is_set_up(client):
    res = await client.get("/api/v1/notifications/whatsapp/status")
    assert res.status_code == 200 and res.json() == {"enabled": False}


async def test_the_app_is_told_whatsapp_is_on_once_it_really_is(client, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "cloud")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "secret-token")
    res = await client.get("/api/v1/notifications/whatsapp/status")
    assert res.json() == {"enabled": True}
    assert "secret-token" not in res.text and "123" not in res.text  # nothing leaks


@pytest.mark.parametrize(
    "setting, value",
    [
        ("WHATSAPP_ENABLED", False),  # switched off
        ("WHATSAPP_ACCESS_TOKEN", ""),  # half set up: would never send
        ("WHATSAPP_TEMPLATE_ORDER_CONFIRMED", ""),  # the main message has no template
    ],
)
async def test_whatsapp_is_not_advertised_when_messages_would_not_go_out(
    client, monkeypatch, setting, value
):
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "cloud")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(settings, setting, value)
    res = await client.get("/api/v1/notifications/whatsapp/status")
    assert res.json() == {"enabled": False}


async def test_it_needs_no_login(client):
    assert (
        await client.get("/api/v1/notifications/whatsapp/status")
    ).status_code == 200
