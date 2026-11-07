"""Orders waiting for payment, against a real PostgreSQL built from the migrations.

SQLite cannot show the things that matter most here: that several requests racing to place the same
order place it exactly once, that expiry run twice at the same moment returns store credit once, and
that migration 0011 leaves every real order alone while tidying only the abandoned ones.
Uses the `pgserver` dev dependency; skipped when it is not installed.
"""

import asyncio
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

pgserver = pytest.importorskip("pgserver")
asyncpg = pytest.importorskip("asyncpg")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import hash_password
from app.credit.models import StoreCredit
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order, OrderStatusLog
from app.order.placement import (
    ALREADY_PLACED,
    PLACED,
    expire_stale_pending_orders,
    place_paid_order,
)
from app.order.websocket_manager import ws_manager
from app.payment.models import Payment, PaymentTransaction
from tests.test_cart_postgres import ROOT, make_database, migrate


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield str(data_dir)
    server.cleanup()


async def _seed_shop(sessions) -> dict:
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
        profile = CustomerProfile(user_id=cust.id, full_name="Asha Kumar")
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
        await s.commit()
        return {
            "user": cust.id,
            "profile": profile.id,
            "brand": brand.id,
            "branch": branch.id,
        }


async def _order(
    sessions,
    shop,
    *,
    status="PENDING_PAYMENT",
    minutes_old=0,
    total=100,
    credit=0,
    paid=False,
    failed_capture=False
) -> uuid.UUID:
    async with sessions() as s:
        order = Order(
            customer_profile_id=shop["profile"],
            branch_id=shop["branch"],
            total_amount=total,
            store_credit_applied=credit,
            status=status,
            delivery_address_snapshot={"branch_name": "Food Court"},
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_old),
        )
        s.add(order)
        await s.flush()
        if paid or failed_capture:
            payment = Payment(
                order_id=order.id,
                customer_profile_id=shop["profile"],
                amount=total - credit,
            )
            s.add(payment)
            await s.flush()
            s.add(
                PaymentTransaction(
                    payment_id=payment.id,
                    transaction_type="CAPTURED",
                    amount=total - credit,
                    status="SUCCESS" if paid else "FAILED",
                )
            )
        await s.commit()
        return order.id


async def test_five_simultaneous_confirmations_place_the_order_exactly_once(
    pg, monkeypatch
):
    """The student's own confirmation, Razorpay's webhook, a retry... all at the same instant."""
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    shop = await _seed_shop(sessions)
    order_id = await _order(sessions, shop)
    kitchen = AsyncMock()
    monkeypatch.setattr(ws_manager, "broadcast_to_branch", kitchen)

    async def confirm() -> str:
        async with sessions() as session:  # one session per request, as in production
            return await place_paid_order(session, order_id, shop["user"])

    results = await asyncio.gather(*[confirm() for _ in range(5)])

    assert sorted(results) == [ALREADY_PLACED] * 4 + [PLACED]
    assert kitchen.await_count == 1  # the kitchen is told once
    async with sessions() as s:
        logs = (
            (
                await s.execute(
                    select(OrderStatusLog).where(OrderStatusLog.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert [(log.previous_status, log.new_status) for log in logs] == [
            ("PENDING_PAYMENT", "PLACED")
        ]
        assert (await s.get(Order, order_id)).status == "PLACED"
    await engine.dispose()


async def test_expiry_running_twice_at_once_returns_the_credit_once(pg, monkeypatch):
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    shop = await _seed_shop(sessions)
    monkeypatch.setattr(ws_manager, "broadcast_to_branch", AsyncMock())
    abandoned = [
        await _order(sessions, shop, minutes_old=45, total=100, credit=40)
        for _ in range(3)
    ]
    await _order(sessions, shop, minutes_old=5)  # still inside the window

    async def sweep() -> int:
        async with sessions() as session:
            return await expire_stale_pending_orders(session, shop["profile"])

    counts = await asyncio.gather(sweep(), sweep(), sweep())

    assert (
        sum(counts) == 3
    )  # each abandoned order cancelled exactly once, whoever got there
    async with sessions() as s:
        statuses = [(await s.get(Order, oid)).status for oid in abandoned]
        assert statuses == ["CANCELLED"] * 3
        credits = (await s.execute(select(StoreCredit))).scalars().all()
        assert len(credits) == 3 and all(
            float(c.initial_amount) == 40.0 for c in credits
        )  # 40 back, per order, once
        pending = (
            await s.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.status == "PENDING_PAYMENT")
            )
        ).scalar_one()
        assert pending == 1
    await engine.dispose()


async def test_migration_0011_tidies_only_orders_that_were_never_paid(pg):
    """Run on a database at 0010 holding every kind of order the live one might."""
    url = await asyncio.to_thread(make_database, pg, "0010")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    shop = await _seed_shop(sessions)
    cases = {
        "old, unpaid": await _order(sessions, shop, status="PLACED", minutes_old=180),
        "old, part paid by credit, rest unpaid": await _order(
            sessions, shop, status="PLACED", minutes_old=180, credit=40
        ),
        "old, only a FAILED payment": await _order(
            sessions, shop, status="PLACED", minutes_old=180, failed_capture=True
        ),
        "old, really paid": await _order(
            sessions, shop, status="PLACED", minutes_old=180, paid=True
        ),
        "recent, unpaid (a checkout in progress)": await _order(
            sessions, shop, status="PLACED", minutes_old=10
        ),
        "old, fully covered by credit": await _order(
            sessions, shop, status="PLACED", minutes_old=180, credit=100
        ),
        "old, already accepted by the kitchen": await _order(
            sessions, shop, status="ACCEPTED", minutes_old=180
        ),
        "old, completed": await _order(
            sessions, shop, status="COMPLETED", minutes_old=500
        ),
    }

    async def statuses() -> dict[str, str]:
        async with sessions() as s:
            return {
                name: (await s.get(Order, oid)).status for name, oid in cases.items()
            }

    await asyncio.to_thread(migrate, url, "head")
    after = await statuses()
    assert after == {
        "old, unpaid": "PENDING_PAYMENT",
        "old, part paid by credit, rest unpaid": "PENDING_PAYMENT",
        "old, only a FAILED payment": "PENDING_PAYMENT",
        "old, really paid": "PLACED",  # never hidden
        "recent, unpaid (a checkout in progress)": "PLACED",  # left alone
        "old, fully covered by credit": "PLACED",  # there was nothing to pay
        "old, already accepted by the kitchen": "ACCEPTED",  # the kitchen has it
        "old, completed": "COMPLETED",
    }

    await asyncio.to_thread(migrate, url, "head")  # running it again changes nothing
    assert await statuses() == after

    # and it can be undone
    result = await asyncio.to_thread(
        lambda: subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "0010"],
            cwd=ROOT,
            env={
                **__import__("os").environ,
                "DATABASE_URL": url,
                "ENVIRONMENT": "test",
            },
            capture_output=True,
            text=True,
            check=False,
        )
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert set((await statuses()).values()) <= {"PLACED", "ACCEPTED", "COMPLETED"}
    await engine.dispose()
