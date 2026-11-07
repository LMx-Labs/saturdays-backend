"""WhatsApp order updates against a real PostgreSQL, built from the migrations.

SQLite cannot show the two things that matter most here: that several requests racing to send the
same message result in exactly ONE message, and that migration 0010 upgrades a database that
already exists. Uses the `pgserver` dev dependency; skipped when it is not installed.
"""

import asyncio
import uuid

import pytest

pgserver = pytest.importorskip("pgserver")
asyncpg = pytest.importorskip("asyncpg")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.config import settings
from app.core.security import hash_password
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.notification.models import Notification
from app.notification.whatsapp import MockWhatsAppProvider
from app.notification.whatsapp_service import ORDER_CONFIRMED, WhatsAppNotifier
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction
from tests.test_cart_postgres import asyncpg_dsn, make_database, migrate


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield str(data_dir)
    server.cleanup()


async def _seed_paid_order(sessions) -> uuid.UUID:
    async with sessions() as s:
        owner = User(
            email="o@x.in",
            password_hash=hash_password("Password123!"),
            role="MerchantOwner",
            is_active=True,
            is_verified=True,
        )
        cust = User(
            email="c@x.in",
            password_hash=hash_password("Password123!"),
            role="Customer",
            is_active=True,
            is_verified=True,
        )
        s.add_all([owner, cust])
        await s.flush()
        profile = CustomerProfile(
            user_id=cust.id,
            full_name="Asha Kumar",
            phone_number="9876543210",
            whatsapp_opt_in=True,
            whatsapp_phone="919876543210",
        )
        merchant = Merchant(
            owner_user_id=owner.id,
            business_name="M",
            legal_entity_name="M",
            fssai_license_number="12345678901234",
            status="ACTIVE",
        )
        s.add_all([profile, merchant])
        await s.flush()
        brand = Brand(merchant_id=merchant.id, name="B")
        s.add(brand)
        await s.flush()
        branch = Branch(brand_id=brand.id, name="Food Court", address_text="x")
        s.add(branch)
        await s.flush()
        order = Order(
            customer_profile_id=profile.id,
            branch_id=branch.id,
            total_amount=190,
            status="PLACED",
            delivery_address_snapshot={"branch_name": "Food Court"},
        )
        s.add(order)
        await s.flush()
        payment = Payment(order_id=order.id, customer_profile_id=profile.id, amount=190)
        s.add(payment)
        await s.flush()
        s.add(
            PaymentTransaction(
                payment_id=payment.id,
                transaction_type="CAPTURED",
                amount=190,
                status="SUCCESS",
            )
        )
        await s.commit()
        return order.id


async def test_five_simultaneous_attempts_send_exactly_one_message(pg, monkeypatch):
    """The student's confirmation, Razorpay's webhook, a retry... all arriving at once."""
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_TEST_ALLOWLIST", "")
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    order_id = await _seed_paid_order(sessions)

    provider = MockWhatsAppProvider()

    async def attempt() -> bool:
        async with sessions() as session:  # one session per request, as in production
            return await WhatsAppNotifier(session, provider=provider).notify(
                order_id, ORDER_CONFIRMED
            )

    results = await asyncio.gather(*[attempt() for _ in range(5)])

    assert sorted(results) == [False, False, False, False, True]
    assert len(provider.sent) == 1
    async with sessions() as s:
        count = (
            await s.execute(select(func.count()).select_from(Notification))
        ).scalar_one()
        row = (await s.execute(select(Notification))).scalar_one()
    assert count == 1
    assert (row.status, row.event, row.order_id) == (
        "SENT",
        "order_confirmed",
        order_id,
    )
    assert row.vendor_message_id.startswith("mock_wamid_")
    await engine.dispose()


async def test_a_message_that_failed_is_not_silently_sent_again(pg, monkeypatch):
    """A failed send keeps its log row, so a retry can't double-send if the first one did arrive."""
    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
    monkeypatch.setattr(settings, "WHATSAPP_TEST_ALLOWLIST", "")
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    order_id = await _seed_paid_order(sessions)
    provider = MockWhatsAppProvider()
    provider.fail_with = RuntimeError("network blip")
    async with sessions() as s:
        assert (
            await WhatsAppNotifier(s, provider=provider).notify(
                order_id, ORDER_CONFIRMED
            )
            is False
        )
    provider.fail_with = None
    async with sessions() as s:
        assert (
            await WhatsAppNotifier(s, provider=provider).notify(
                order_id, ORDER_CONFIRMED
            )
            is False
        )
    assert provider.sent == []
    async with sessions() as s:
        row = (await s.execute(select(Notification))).scalar_one()
    assert row.status == "FAILED" and "network blip" in row.error
    await engine.dispose()


async def test_migration_0010_upgrades_an_existing_database(pg):
    """A database already at 0009 (the live one) gains the new columns and index, and the
    migration can be run again without harm."""
    url = await asyncio.to_thread(make_database, pg, "0009")
    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:
        before = {
            r["column_name"]
            for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'customer_profiles'"
            )
        }
        assert "whatsapp_opt_in" not in before
    finally:
        await conn.close()

    await asyncio.to_thread(migrate, url, "head")
    await asyncio.to_thread(migrate, url, "head")  # again: nothing breaks

    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:
        cust = {
            r["column_name"]: r
            for r in await conn.fetch(
                "SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'customer_profiles'"
            )
        }
        assert (
            cust["whatsapp_opt_in"]["is_nullable"] == "NO"
            and "false" in cust["whatsapp_opt_in"]["column_default"].lower()
        )
        assert {"whatsapp_opt_in_at", "whatsapp_phone"} <= set(cust)
        notif = {
            r["column_name"]
            for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'notifications'"
            )
        }
        assert {"order_id", "event", "error", "delivered_at", "read_at"} <= notif
        index = await conn.fetchval(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_notifications_order_channel_event'"
        )
        assert "UNIQUE" in index and "order_id IS NOT NULL" in index
    finally:
        await conn.close()


async def test_existing_customers_start_with_whatsapp_off(pg):
    """Customers who existed before this feature must not be opted in by the upgrade."""
    url = await asyncio.to_thread(make_database, pg, "0009")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, is_active, is_verified) VALUES (gen_random_uuid(), 'old@x.in', 'x', 'Customer', true, true)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO customer_profiles (id, user_id, full_name, phone_number, created_at, updated_at) SELECT gen_random_uuid(), id, 'Old Customer', '9876543210', now(), now() FROM users WHERE email = 'old@x.in'"
            )
        )
    await asyncio.to_thread(migrate, url, "head")
    async with engine.begin() as conn:
        from sqlalchemy import text

        row = (
            await conn.execute(
                text("SELECT whatsapp_opt_in, whatsapp_phone FROM customer_profiles")
            )
        ).one()
    assert row.whatsapp_opt_in is False and row.whatsapp_phone is None
    await engine.dispose()
