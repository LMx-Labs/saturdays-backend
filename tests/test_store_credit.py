import uuid

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
from app.payment.models import Payment, PaymentTransaction


def _hdr(user: User, branch_id: uuid.UUID | None = None) -> dict:
    extra = {"email": user.email}
    if branch_id:
        extra["branch_id"] = str(branch_id)
    token = create_access_token(str(user.id), user.role, extra_claims=extra)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def shop(db_session: AsyncSession):
    def mk(email, role):
        return User(
            email=email,
            password_hash=hash_password("Password123!"),
            role=role,
            is_active=True,
        )

    cust, cust2, staff, admin, owner = (
        mk("c1@s.com", "Customer"),
        mk("c2@s.com", "Customer"),
        mk("st@s.com", "BranchManager"),
        mk("ad@s.com", "PlatformAdmin"),
        mk("ow@s.com", "MerchantOwner"),
    )
    db_session.add_all([cust, cust2, staff, admin, owner])
    await db_session.flush()
    p1 = CustomerProfile(user_id=cust.id, full_name="C One")
    p2 = CustomerProfile(user_id=cust2.id, full_name="C Two")
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Shop",
        legal_entity_name="Shop LLC",
        fssai_license_number="11223344556677",
        status="APPROVED",
        bank_account_number="123456789012",
        bank_ifsc_code="HDFC0001234",
    )
    db_session.add_all([p1, p2, merchant])
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Shop Brand")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Shop Branch", address_text="Gate")
    other_branch = Branch(brand_id=brand.id, name="Other", address_text="Gate 2")
    db_session.add_all([branch, other_branch])
    await db_session.flush()
    branch.closing_time = branch.opening_time
    staff.branch_id = branch.id
    db_session.add(Kitchen(branch_id=branch.id, name="Main Kitchen", is_active=True))
    menu = Menu(branch_id=branch.id, name="Menu")
    db_session.add(menu)
    await db_session.flush()
    cat = MenuCategory(menu_id=menu.id, name="Food")
    db_session.add(cat)
    await db_session.flush()
    item = MenuItem(category_id=cat.id, name="Meal", base_price=100.00)
    db_session.add(item)
    await db_session.flush()
    db_session.add(
        InventoryItem(
            branch_id=branch.id, menu_item_id=item.id, quantity=10, is_in_stock=True
        )
    )
    await db_session.commit()
    return {
        "cust": cust,
        "cust2": cust2,
        "staff": staff,
        "admin": admin,
        "owner": owner,
        "profile": p1,
        "profile2": p2,
        "merchant": merchant,
        "brand": brand,
        "branch": branch,
        "other_branch": other_branch,
        "item": item,
    }


async def place_order(client, ctx, use_credit=False):
    resp = await client.post(
        "/api/v1/orders",
        headers={**_hdr(ctx["cust"]), "Idempotency-Key": f"credit-{uuid.uuid4()}"},
        json={
            "branch_id": str(ctx["branch"].id),
            "items": [{"menu_item_id": str(ctx["item"].id), "quantity": 1}],
            "delivery_address_snapshot": {"line": "Hostel 4"},
            "use_store_credit": use_credit,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def grant_credit(client, ctx, amount=100.0):
    response = await client.post(
        "/api/v1/store-credits/grant",
        headers=_hdr(ctx["admin"]),
        json={
            "customer_profile_id": str(ctx["profile"].id),
            "brand_id": str(ctx["brand"].id),
            "amount": amount,
            "reason": "GOODWILL",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_legacy_captured_order_cannot_cancel_without_refund_policy(
    client: AsyncClient, shop: dict, db_session: AsyncSession
):
    order = await place_order(client, shop)
    payment = Payment(
        order_id=uuid.UUID(order["id"]),
        customer_profile_id=shop["profile"].id,
        amount=100,
    )
    db_session.add(payment)
    await db_session.flush()
    db_session.add(
        PaymentTransaction(
            payment_id=payment.id,
            transaction_type="CAPTURED",
            amount=100,
            status="SUCCESS",
            razorpay_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        )
    )
    await db_session.commit()

    cancel = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_hdr(shop["cust"])
    )
    assert cancel.status_code == 409
    assert cancel.json()["error_code"] == "PAID_CANCELLATION_REQUIRES_POLICY"

    credits = await client.get("/api/v1/store-credits", headers=_hdr(shop["cust"]))
    assert credits.json() == []
    refund = await client.post(
        f"/api/v1/payments/{payment.id}/refund",
        headers=_hdr(shop["staff"]),
        json={"amount": 100.0},
    )
    assert refund.status_code in {400, 403, 503}


@pytest.mark.asyncio
async def test_cancel_unpaid_order_issues_no_credit(client: AsyncClient, shop: dict):
    order = await place_order(client, shop)
    await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_hdr(shop["cust"])
    )
    credits = await client.get("/api/v1/store-credits", headers=_hdr(shop["cust"]))
    assert credits.json() == []


@pytest.mark.asyncio
async def test_staff_rejection_releases_unpaid_stock_without_credit(
    client: AsyncClient, shop: dict
):
    order = await place_order(client, shop)
    res = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=_hdr(shop["staff"], shop["branch"].id),
        json={"status": "CANCELLED"},
    )
    assert res.status_code == 200
    credits = await client.get("/api/v1/store-credits", headers=_hdr(shop["cust"]))
    assert credits.json() == []


@pytest.mark.asyncio
async def test_credit_is_redeemed_on_next_order_at_same_brand(
    client: AsyncClient, shop: dict
):
    await grant_credit(client, shop)

    second = await place_order(client, shop, use_credit=True)
    assert second["store_credit_applied"] == 100.0

    bal = await client.get(
        f"/api/v1/store-credits/balance?brand_id={shop['brand'].id}",
        headers=_hdr(shop["cust"]),
    )
    assert bal.json()["available_balance"] == 0.0

    # Cancelling the credit-paid order restores the value as fresh credit
    await client.post(
        f"/api/v1/orders/{second['id']}/cancel", headers=_hdr(shop["cust"])
    )
    bal = await client.get(
        f"/api/v1/store-credits/balance?brand_id={shop['brand'].id}",
        headers=_hdr(shop["cust"]),
    )
    assert bal.json()["available_balance"] == 100.0


@pytest.mark.asyncio
async def test_credit_not_spent_unless_requested_and_not_by_other_customers(
    client: AsyncClient, shop: dict
):
    await grant_credit(client, shop)

    plain = await place_order(client, shop, use_credit=False)
    assert plain["store_credit_applied"] == 0.0

    # another customer sees nothing
    other = await client.get(
        f"/api/v1/store-credits/balance?brand_id={shop['brand'].id}",
        headers=_hdr(shop["cust2"]),
    )
    assert other.json()["available_balance"] == 0.0


@pytest.mark.asyncio
async def test_order_authorization(
    client: AsyncClient, shop: dict, db_session: AsyncSession
):
    order = await place_order(client, shop)

    # A customer cannot advance the kitchen workflow (which would trigger payouts)
    res = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=_hdr(shop["cust"]),
        json={"status": "ACCEPTED"},
    )
    assert res.status_code == 403

    # another customer cannot cancel or read it
    assert (
        await client.post(
            f"/api/v1/orders/{order['id']}/cancel", headers=_hdr(shop["cust2"])
        )
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=_hdr(shop["cust2"]))
    ).status_code == 403

    # Current database assignment, not the branch claim in the token, controls access.
    shop["staff"].branch_id = shop["other_branch"].id
    await db_session.commit()
    wrong = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=_hdr(shop["staff"], shop["branch"].id),
        json={"status": "ACCEPTED"},
    )
    assert wrong.status_code == 403
    shop["staff"].branch_id = shop["branch"].id
    await db_session.commit()
    ok = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=_hdr(shop["staff"], shop["branch"].id),
        json={"status": "ACCEPTED"},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_admin_manual_grant(client: AsyncClient, shop: dict):
    res = await client.post(
        "/api/v1/store-credits/grant",
        headers=_hdr(shop["admin"]),
        json={
            "customer_profile_id": str(shop["profile"].id),
            "brand_id": str(shop["brand"].id),
            "amount": 50,
            "reason": "GOODWILL",
        },
    )
    assert res.status_code == 201
    denied = await client.post(
        "/api/v1/store-credits/grant",
        headers=_hdr(shop["cust"]),
        json={
            "customer_profile_id": str(shop["profile"].id),
            "brand_id": str(shop["brand"].id),
            "amount": 50,
            "reason": "x",
        },
    )
    assert denied.status_code == 403
