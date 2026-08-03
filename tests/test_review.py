import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import hash_password
from app.customer.models import CustomerProfile
from app.merchant.models import Merchant
from app.order.models import Order


@pytest.fixture
async def setup_review_fixture(db_session: AsyncSession):
    # Customer
    user = User(
        email="reviewer@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    profile = CustomerProfile(user_id=user.id, full_name="Reviewer User")
    db_session.add(profile)
    await db_session.flush()

    # Merchant & Brand & Branch
    merchant = Merchant(
        owner_user_id=user.id,
        business_name="Review Store",
        legal_entity_name="Review Store LLC",
        fssai_license_number="12345678901234",
    )
    db_session.add(merchant)
    await db_session.flush()

    brand = Brand(merchant_id=merchant.id, name="Review Brand")
    db_session.add(brand)
    await db_session.flush()

    branch = Branch(brand_id=brand.id, name="Review Branch", address_text="Review Way")
    db_session.add(branch)
    await db_session.flush()

    # Completed order (Eligible for review)
    completed_order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        order_number="ORD-REV-001",
        subtotal=200.0,
        total_amount=200.0,
        status="COMPLETED",
        delivery_address_snapshot={"address": "Campus Hostel"},
    )

    # Pending order (Ineligible for review)
    pending_order = Order(
        customer_profile_id=profile.id,
        branch_id=branch.id,
        order_number="ORD-REV-002",
        subtotal=150.0,
        total_amount=150.0,
        status="PLACED",
        delivery_address_snapshot={"address": "Campus Hostel"},
    )

    db_session.add_all([completed_order, pending_order])
    await db_session.commit()

    return {
        "user": user,
        "profile": profile,
        "branch": branch,
        "completed_order": completed_order,
        "pending_order": pending_order,
    }


async def get_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_verified_purchase_and_rating_range(client: AsyncClient, setup_review_fixture: dict):
    fixture = setup_review_fixture
    headers = await get_headers(client, fixture["user"].email)

    # Attempt to review a pending order (Ineligible - INV-0007)
    pending_payload = {
        "order_id": str(fixture["pending_order"].id),
        "rating": 5,
        "comment": "Great food!",
    }
    pending_resp = await client.post("/api/v1/reviews", headers=headers, json=pending_payload)
    assert pending_resp.status_code == 422
    assert pending_resp.json()["error_code"] == "ORDER_NOT_COMPLETED"

    # Attempt review with invalid rating > 5 (INV-REV-001)
    invalid_rating_payload = {
        "order_id": str(fixture["completed_order"].id),
        "rating": 6,
        "comment": "Too high",
    }
    invalid_resp = await client.post(
        "/api/v1/reviews", headers=headers, json=invalid_rating_payload
    )
    assert invalid_resp.status_code == 422

    # Submit valid review for completed order
    valid_payload = {
        "order_id": str(fixture["completed_order"].id),
        "rating": 5,
        "comment": "Delicious food and fast delivery!",
    }
    resp = await client.post("/api/v1/reviews", headers=headers, json=valid_payload)
    assert resp.status_code == 201
    rev_data = resp.json()
    assert rev_data["rating"] == 5
    assert rev_data["comment"] == "Delicious food and fast delivery!"

    # Attempt duplicate review for same order
    dup_resp = await client.post("/api/v1/reviews", headers=headers, json=valid_payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error_code"] == "REVIEW_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_review_reply_moderation_and_summary(client: AsyncClient, setup_review_fixture: dict):
    fixture = setup_review_fixture
    headers = await get_headers(client, fixture["user"].email)

    # Create review
    review_resp = await client.post(
        "/api/v1/reviews",
        headers=headers,
        json={
            "order_id": str(fixture["completed_order"].id),
            "rating": 4,
            "comment": "Very good experience.",
        },
    )
    assert review_resp.status_code == 201
    review_id = review_resp.json()["id"]

    # Merchant reply
    reply_resp = await client.post(
        f"/api/v1/reviews/{review_id}/reply",
        json={"merchant_reply": "Thank you for dining with us!"},
    )
    assert reply_resp.status_code == 200
    assert reply_resp.json()["merchant_reply"] == "Thank you for dining with us!"

    # Rating summary check
    branch_id = str(fixture["branch"].id)
    summary_resp = await client.get(f"/api/v1/branches/{branch_id}/rating-summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["average_rating"] == 4.0
    assert summary["total_reviews"] == 1
    assert summary["rating_distribution"]["4"] == 1

    # Moderate review (Hide)
    mod_resp = await client.put(
        f"/api/v1/reviews/{review_id}/moderate", json={"is_hidden": True}
    )
    assert mod_resp.status_code == 200
    assert mod_resp.json()["is_hidden"] is True

    # List public branch reviews (hidden review should be omitted)
    list_resp = await client.get(f"/api/v1/branches/{branch_id}/reviews")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0
