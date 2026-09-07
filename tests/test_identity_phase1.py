import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.roles import Role, normalize_role
from app.core.security import hash_password
from app.merchant.models import Merchant


async def provision_user(
    db_session: AsyncSession, email: str, role: str, password: str = "Password123!"
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def login(client: AsyncClient, email: str) -> tuple[dict[str, str], dict]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


@pytest.mark.asyncio
async def test_public_registration_rejects_role_escalation_and_assigns_customer(
    client: AsyncClient,
):
    rejected = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "escalation@example.com",
            "password": "Password123!",
            "role": "PlatformAdmin",
        },
    )
    assert rejected.status_code == 403

    accepted = await client.post(
        "/api/v1/auth/register",
        json={"email": "customer@example.com", "password": "Password123!"},
    )
    assert accepted.status_code == 201
    assert accepted.json()["user"]["role"] == Role.CUSTOMER.value


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout_revocation(client: AsyncClient):
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": "rotation@example.com", "password": "Password123!"},
    )
    first = registered.json()["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["refresh_token"]
    assert second != first
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": second})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    ).status_code == 401


@pytest.mark.asyncio
async def test_email_verification_and_password_reset_tokens_are_single_use(
    client: AsyncClient,
):
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": "tokens@example.com", "password": "Password123!"},
    )
    original_refresh = registered.json()["refresh_token"]
    resent = await client.post(
        "/api/v1/auth/verification/resend", json={"email": "tokens@example.com"}
    )
    verification_token = resent.json()["preview_token"]
    assert (
        await client.post(
            "/api/v1/auth/verify-email", json={"token": verification_token}
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/verify-email", json={"token": verification_token}
        )
    ).status_code == 422

    forgot = await client.post(
        "/api/v1/auth/password/forgot", json={"email": "tokens@example.com"}
    )
    reset_token = forgot.json()["preview_token"]
    assert (
        await client.post(
            "/api/v1/auth/password/reset",
            json={"token": reset_token, "new_password": "NewPassword123!"},
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/auth/password/reset",
            json={"token": reset_token, "new_password": "AnotherPassword123!"},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": original_refresh}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "tokens@example.com", "password": "NewPassword123!"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_admin_provisioning_and_staff_invitation_scope(
    client: AsyncClient, db_session: AsyncSession
):
    admin = await provision_user(
        db_session, "identity-admin@example.com", Role.PLATFORM_ADMIN.value
    )
    owner = await provision_user(
        db_session, "identity-owner@example.com", Role.MERCHANT_OWNER.value
    )
    other_owner = await provision_user(
        db_session, "other-owner@example.com", Role.MERCHANT_OWNER.value
    )
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Identity Merchant",
        legal_entity_name="Identity Merchant Pvt Ltd",
        fssai_license_number="12345678901234",
    )
    other_merchant = Merchant(
        owner_user_id=other_owner.id,
        business_name="Other Merchant",
        legal_entity_name="Other Merchant Pvt Ltd",
        fssai_license_number="99999999999999",
    )
    db_session.add_all([merchant, other_merchant])
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Owned Brand")
    other_brand = Brand(merchant_id=other_merchant.id, name="Other Brand")
    db_session.add_all([brand, other_brand])
    await db_session.flush()
    branch = Branch(
        brand_id=brand.id, name="Owned", address_text="Campus One"
    )
    other_branch = Branch(
        brand_id=other_brand.id, name="Other", address_text="Campus Two"
    )
    db_session.add_all([branch, other_branch])
    await db_session.commit()

    admin_headers, _ = await login(client, admin.email)
    created = await client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "provisioned@example.com",
            "password": "Password123!",
            "role": "MerchantOwner",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == Role.MERCHANT_OWNER.value

    owner_headers, _ = await login(client, owner.email)
    out_of_scope = await client.post(
        "/api/v1/merchants/staff/invitations",
        headers=owner_headers,
        json={
            "email": "staff@example.com",
            "role": "KitchenStaff",
            "branch_ids": [str(other_branch.id)],
        },
    )
    assert out_of_scope.status_code == 422

    invitation = await client.post(
        "/api/v1/merchants/staff/invitations",
        headers=owner_headers,
        json={
            "email": "staff@example.com",
            "role": "KitchenStaff",
            "branch_ids": [str(branch.id)],
        },
    )
    assert invitation.status_code == 201
    token = invitation.json()["preview_token"]
    accepted = await client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "password": "Password123!"},
    )
    assert accepted.status_code == 201
    assert accepted.json()["user"]["role"] == Role.KITCHEN_STAFF.value
    staff = await client.get("/api/v1/merchants/staff", headers=owner_headers)
    assert staff.status_code == 200
    assert staff.json()[0]["branch_ids"] == [str(branch.id)]


def test_role_normalization():
    assert normalize_role("Admin") == Role.PLATFORM_ADMIN.value
    assert normalize_role("platformadmin") == Role.PLATFORM_ADMIN.value
