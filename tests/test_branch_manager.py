import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import decode_token, hash_password
from app.merchant.models import Merchant


@pytest.fixture
async def onboarding(db_session: AsyncSession):
    admin = User(
        email="sa@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="PlatformAdmin",
        is_active=True,
    )
    owner = User(
        email="owner@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="MerchantOwner",
        is_active=True,
    )
    db_session.add_all([admin, owner])
    await db_session.flush()
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Cafe",
        legal_entity_name="Cafe LLC",
        fssai_license_number="11223344556677",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Cafe Brand")
    db_session.add(brand)
    await db_session.flush()
    branch_a = Branch(brand_id=brand.id, name="Cafe A", address_text="Gate 1")
    branch_b = Branch(brand_id=brand.id, name="Cafe B", address_text="Gate 2")
    db_session.add_all([branch_a, branch_b])
    await db_session.commit()
    return {"admin": admin, "branch_a": branch_a, "branch_b": branch_b, "brand": brand}


async def _login(client: AsyncClient, email: str, password: str = "Password123!"):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_admin_creates_branch_manager_with_branch_id(
    client: AsyncClient, onboarding: dict
):
    admin_headers = {
        "Authorization": f"Bearer {(await _login(client, 'sa@saturdays.com'))['access_token']}"
    }
    branch = onboarding["branch_a"]

    resp = await client.post(
        "/api/v1/admin/branch-managers",
        headers=admin_headers,
        json={
            "email": "Manager@Saturdays.com",
            "password": "Password123!",
            "branch_id": str(branch.id),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["branch_id"] == str(branch.id)
    assert data["branch_name"] == "Cafe A"
    assert data["brand_id"] == str(onboarding["brand"].id)
    assert data["role"] == "BranchManager"

    # The manager's own login exposes the branch id (body + JWT claim + /auth/me)
    login = await _login(client, "manager@saturdays.com")
    assert login["user"]["branch_id"] == str(branch.id)
    assert decode_token(login["access_token"])["branch_id"] == str(branch.id)
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me.json()["branch_id"] == str(branch.id)

    # Refreshed tokens keep the claim
    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert decode_token(refreshed.json()["access_token"])["branch_id"] == str(branch.id)


@pytest.mark.asyncio
async def test_branch_manager_listing_reassign_and_validation(
    client: AsyncClient, onboarding: dict
):
    headers = {
        "Authorization": f"Bearer {(await _login(client, 'sa@saturdays.com'))['access_token']}"
    }
    a, b = onboarding["branch_a"], onboarding["branch_b"]
    created = await client.post(
        "/api/v1/admin/branch-managers",
        headers=headers,
        json={
            "email": "m1@saturdays.com",
            "password": "Password123!",
            "branch_id": str(a.id),
        },
    )
    user_id = created.json()["user_id"]

    # duplicate email -> 409, unknown branch -> 404
    dup = await client.post(
        "/api/v1/admin/branch-managers",
        headers=headers,
        json={
            "email": "M1@saturdays.com",
            "password": "Password123!",
            "branch_id": str(a.id),
        },
    )
    assert dup.status_code == 409
    missing = await client.post(
        "/api/v1/admin/branch-managers",
        headers=headers,
        json={
            "email": "m2@saturdays.com",
            "password": "Password123!",
            "branch_id": str(uuid.uuid4()),
        },
    )
    assert missing.status_code == 404

    listed = await client.get(
        f"/api/v1/admin/branch-managers?branch_id={a.id}", headers=headers
    )
    assert [m["email"] for m in listed.json()] == ["m1@saturdays.com"]

    moved = await client.put(
        f"/api/v1/admin/branch-managers/{user_id}/branch",
        headers=headers,
        json={"branch_id": str(b.id)},
    )
    assert moved.status_code == 200
    assert moved.json()["branch_id"] == str(b.id)
    assert (await _login(client, "m1@saturdays.com"))["user"]["branch_id"] == str(b.id)

    empty = await client.get(
        f"/api/v1/admin/branch-managers?branch_id={a.id}", headers=headers
    )
    assert empty.json() == []


@pytest.mark.asyncio
async def test_only_platform_admin_can_onboard_branch_managers(
    client: AsyncClient, onboarding: dict
):
    owner = await _login(client, "owner@saturdays.com")
    resp = await client.post(
        "/api/v1/admin/branch-managers",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
        json={
            "email": "x@saturdays.com",
            "password": "Password123!",
            "branch_id": str(onboarding["branch_a"].id),
        },
    )
    assert resp.status_code == 403
