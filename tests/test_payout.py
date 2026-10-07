import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import create_access_token, hash_password
from app.customer.models import CustomerProfile
from app.main import app as fastapi_app
from app.merchant.models import Merchant
from app.order.models import Order
from app.payment.models import Payment, PaymentTransaction
from app.payment.razorpay_adapter import RazorpayAdapter
from app.payout.gateway import GatewayPayout, PayoutGatewayError, RazorpayXClient
from app.payout.models import Payout, PayoutItem
from app.payout.router import get_payout_service
from app.payout.service import PayoutService
from app.subscription.models import PlatformCommission

TODAY = datetime.now(UTC).date()


def hdr(user: User) -> dict:
    return {
        "Authorization": "Bearer "
        + create_access_token(str(user.id), user.role, {"email": user.email})
    }


class FakeGateway(RazorpayXClient):
    def __init__(self, fail_with: PayoutGatewayError | None = None, status="processed"):
        super().__init__(simulate=True)
        self.fail_with = fail_with
        self.status = status
        self.payout_calls: list[dict] = []

    async def create_payout(self, **kwargs):
        self.payout_calls.append(kwargs)
        if self.fail_with:
            raise self.fail_with
        return GatewayPayout(
            id=f"pout_{len(self.payout_calls)}", status=self.status, utr="UTR123"
        )


@pytest.fixture
async def world(db_session: AsyncSession):
    def mk(email, role):
        return User(
            email=email,
            password_hash=hash_password("x" * 10),
            role=role,
            is_active=True,
        )

    admin, owner, cust, owner2 = (
        mk("a@p.com", "PlatformAdmin"),
        mk("o@p.com", "MerchantOwner"),
        mk("c@p.com", "Customer"),
        mk("o2@p.com", "MerchantOwner"),
    )
    db_session.add_all([admin, owner, cust, owner2])
    await db_session.flush()
    profile = CustomerProfile(user_id=cust.id, full_name="Cust")
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="M1",
        legal_entity_name="M1 LLC",
        fssai_license_number="11223344556677",
        status="APPROVED",
        bank_account_number="123456789012",
        bank_ifsc_code="HDFC0001234",
    )
    merchant2 = Merchant(
        owner_user_id=owner2.id,
        business_name="M2 no bank",
        legal_entity_name="M2 LLC",
        fssai_license_number="11223344556678",
        status="APPROVED",
    )
    db_session.add_all([profile, merchant, merchant2])
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="B1")
    brand2 = Brand(merchant_id=merchant2.id, name="B2")
    db_session.add_all([brand, brand2])
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Br1", address_text="x")
    branch2 = Branch(brand_id=brand2.id, name="Br2", address_text="x")
    db_session.add_all([branch, branch2])
    await db_session.commit()
    return {
        "admin": admin,
        "owner": owner,
        "owner2": owner2,
        "profile": profile,
        "merchant": merchant,
        "merchant2": merchant2,
        "branch": branch,
        "branch2": branch2,
    }


async def add_order(
    db: AsyncSession,
    w: dict,
    total=100.0,
    status="COMPLETED",
    paid: float | None = 100.0,
    credit=0.0,
    branch_key="branch",
) -> Order:
    order = Order(
        customer_profile_id=w["profile"].id,
        branch_id=w[branch_key].id,
        total_amount=total,
        store_credit_applied=credit,
        status=status,
        delivery_address_snapshot={"a": 1},
    )
    db.add(order)
    await db.flush()
    if paid:
        pay = Payment(
            order_id=order.id, customer_profile_id=w["profile"].id, amount=paid
        )
        db.add(pay)
        await db.flush()
        db.add(
            PaymentTransaction(
                payment_id=pay.id,
                transaction_type="CAPTURED",
                amount=paid,
                status="SUCCESS",
                razorpay_payment_id=f"pay_{uuid.uuid4().hex[:8]}",
            )
        )
    await db.commit()
    return order


@pytest.fixture
def gateway():
    gw = FakeGateway()
    yield gw
    fastapi_app.dependency_overrides.pop(get_payout_service, None)


def use_gateway(gw: FakeGateway, db: AsyncSession):
    fastapi_app.dependency_overrides[get_payout_service] = lambda: PayoutService(
        db, gateway=gw
    )


async def run(client, w, **body):
    return await client.post("/api/v1/payouts/run", headers=hdr(w["admin"]), json=body)


@pytest.mark.asyncio
async def test_daily_payout_pays_net_of_commission(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    o1 = await add_order(db_session, world, total=100.0)
    o2 = await add_order(
        db_session, world, total=300.0, paid=330.0
    )  # tax/delivery extra

    resp = await run(client, world)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["merchants_paid"] == 1
    p = data["payouts"][0]
    # default 5% commission: gross 400, commission 20, net 380
    assert (p["gross_amount"], p["commission_amount"], p["net_amount"]) == (
        400.0,
        20.0,
        380.0,
    )
    assert p["status"] == "PROCESSED"
    assert p["utr"] == "UTR123"
    assert gateway.payout_calls[0]["amount_paise"] == 38000
    assert gateway.payout_calls[0]["idempotency_key"].endswith(":0")

    items = (await db_session.execute(select(PayoutItem))).scalars().all()
    assert {i.order_id for i in items} == {o1.id, o2.id}
    comms = (await db_session.execute(select(PlatformCommission))).scalars().all()
    assert len(comms) == 2

    # Running again the same day pays nothing new (idempotent)
    again = await run(client, world)
    assert again.json()["merchants_paid"] == 0
    assert len(gateway.payout_calls) == 1
    assert len((await db_session.execute(select(Payout))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_unpaid_or_unfinished_orders_are_not_paid(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    await add_order(db_session, world, status="PREPARING")
    await add_order(db_session, world, status="CANCELLED")
    await add_order(db_session, world, paid=None)  # completed but no captured payment
    await add_order(db_session, world, total=100.0, paid=40.0)  # underpaid

    data = (await run(client, world)).json()
    assert data["merchants_paid"] == 0
    assert gateway.payout_calls == []


@pytest.mark.asyncio
async def test_store_credit_covered_order_is_paid_to_merchant(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    await add_order(db_session, world, total=100.0, paid=None, credit=100.0)
    data = (await run(client, world)).json()
    assert data["payouts"][0]["net_amount"] == 95.0


@pytest.mark.asyncio
async def test_dry_run_creates_nothing(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    await add_order(db_session, world)
    data = (await run(client, world, dry_run=True)).json()
    assert data["dry_run"] is True
    assert data["total_net_amount"] == 95.0
    assert gateway.payout_calls == []
    assert (await db_session.execute(select(Payout))).scalars().all() == []
    assert (await db_session.execute(select(PlatformCommission))).scalars().all() == []


@pytest.mark.asyncio
async def test_missing_bank_details_skipped_with_reason(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    await add_order(db_session, world, branch_key="branch2")
    data = (await run(client, world)).json()
    assert data["merchants_paid"] == 0
    assert "bank" in data["skipped"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_failed_payout_is_retried_with_new_idempotency_key(
    client: AsyncClient, db_session: AsyncSession, world: dict
):
    gw = FakeGateway(
        fail_with=PayoutGatewayError("Insufficient funds", retryable=False)
    )
    use_gateway(gw, db_session)
    await add_order(db_session, world)

    data = (await run(client, world)).json()
    payout = data["payouts"][0]
    assert payout["status"] == "FAILED"
    assert "Insufficient" in payout["failure_reason"]
    first_key = gw.payout_calls[0]["idempotency_key"]

    gw.fail_with = None
    retry = await client.post(
        f"/api/v1/payouts/{payout['id']}/retry", headers=hdr(world["admin"])
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "PROCESSED"
    assert gw.payout_calls[1]["idempotency_key"] != first_key
    assert len(retry.json()["items"]) == 1  # same order, never duplicated

    # a processed payout cannot be retried
    again = await client.post(
        f"/api/v1/payouts/{payout['id']}/retry", headers=hdr(world["admin"])
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_network_error_keeps_idempotency_key_for_safe_resend(
    client: AsyncClient, db_session: AsyncSession, world: dict
):
    gw = FakeGateway(fail_with=PayoutGatewayError("timeout", retryable=True))
    use_gateway(gw, db_session)
    await add_order(db_session, world)

    payout = (await run(client, world)).json()["payouts"][0]
    assert payout["status"] == "PENDING"

    gw.fail_with = None
    next_run = (await run(client, world)).json()
    assert next_run["payouts"][0]["status"] == "PROCESSED"
    assert (
        gw.payout_calls[0]["idempotency_key"] == gw.payout_calls[1]["idempotency_key"]
    )


@pytest.mark.asyncio
async def test_payout_webhook_updates_status_and_rejects_bad_signature(
    client: AsyncClient, db_session: AsyncSession, world: dict
):
    gw = FakeGateway(status="processing")
    use_gateway(gw, db_session)
    await add_order(db_session, world)
    payout = (await run(client, world)).json()["payouts"][0]
    assert payout["status"] == "PROCESSING"

    adapter = RazorpayAdapter()

    def signed(event: str, status: str):
        body = json.dumps(
            {
                "event": event,
                "payload": {
                    "payout": {
                        "entity": {
                            "id": payout["razorpay_payout_id"],
                            "status": status,
                            "utr": "UTR999",
                        }
                    }
                },
            }
        ).encode()
        sig = hmac.new(
            adapter.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return body, sig

    body, sig = signed("payout.processed", "processed")
    bad = await client.post(
        "/api/v1/payouts/webhook",
        content=body,
        headers={"X-Razorpay-Signature": "0" * 64},
    )
    assert bad.status_code == 400

    ok = await client.post(
        "/api/v1/payouts/webhook", content=body, headers={"X-Razorpay-Signature": sig}
    )
    assert ok.status_code == 200
    assert ok.json()["payout_status"] == "PROCESSED"
    detail = await client.get(
        f"/api/v1/payouts/{payout['id']}", headers=hdr(world["admin"])
    )
    assert detail.json()["utr"] == "UTR999"

    # a later duplicate "failed" must not downgrade a processed payout
    body, sig = signed("payout.failed", "failed")
    await client.post(
        "/api/v1/payouts/webhook", content=body, headers={"X-Razorpay-Signature": sig}
    )
    detail = await client.get(
        f"/api/v1/payouts/{payout['id']}", headers=hdr(world["admin"])
    )
    assert detail.json()["status"] == "PROCESSED"


@pytest.mark.asyncio
async def test_merchant_sees_only_own_payouts_and_non_admin_cannot_run(
    client: AsyncClient, db_session: AsyncSession, world: dict, gateway
):
    use_gateway(gateway, db_session)
    await add_order(db_session, world)
    payout = (await run(client, world)).json()["payouts"][0]

    mine = await client.get("/api/v1/payouts/me", headers=hdr(world["owner"]))
    assert [p["id"] for p in mine.json()] == [payout["id"]]
    detail = await client.get(
        f"/api/v1/payouts/me/{payout['id']}", headers=hdr(world["owner"])
    )
    assert len(detail.json()["items"]) == 1

    theirs = await client.get("/api/v1/payouts/me", headers=hdr(world["owner2"]))
    assert theirs.json() == []
    forbidden = await client.get(
        f"/api/v1/payouts/me/{payout['id']}", headers=hdr(world["owner2"])
    )
    assert forbidden.status_code == 404

    denied = await client.post(
        "/api/v1/payouts/run", headers=hdr(world["owner"]), json={}
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_simulated_gateway_default_moves_no_money(
    db_session: AsyncSession, world: dict
):
    await add_order(db_session, world)
    result = await PayoutService(db_session).run_daily_payouts()
    assert result.payouts[0].status == "PROCESSED"
    assert result.payouts[0].razorpay_payout_id.startswith("pout_sim_")
