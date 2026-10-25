import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.security import hash_password
from app.merchant.models import Merchant
from tests.conftest import seed_user_login


@pytest.fixture
async def staff_accounts_setup(db_session: AsyncSession):
    admin = User(
        email="accounts_admin@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="PlatformAdmin",
        is_active=True,
        is_verified=True,
    )
    door = User(
        email="door_staff@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Admin",
        is_active=True,
        is_verified=True,
    )
    owner = User(
        email="resto_owner@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="MerchantOwner",
        is_active=True,
        is_verified=True,
    )
    db_session.add_all([admin, door, owner])
    await db_session.flush()
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Accounts Cafe",
        legal_entity_name="Accounts Cafe LLC",
        fssai_license_number="11223344556677",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Accounts Brand")
    db_session.add(brand)
    await db_session.flush()
    branch = Branch(brand_id=brand.id, name="Accounts Branch", address_text="Gate 1")
    db_session.add(branch)
    await db_session.commit()
    return {
        "admin": admin,
        "door": door,
        "owner": owner,
        "merchant": merchant,
        "brand": brand,
        "branch": branch,
    }


async def _admin_headers(client: AsyncClient) -> dict:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "accounts_admin@saturdays.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_public_register_rejects_staff_roles(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky_admin@saturdays.com",
            "password": "Password123!",
            "role": "PlatformAdmin",
        },
    )
    # The request schema rejects privileged roles before reaching the service.
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_platform_admin_lists_staff_and_restaurant_accounts(
    client: AsyncClient, staff_accounts_setup: dict
):
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/admin/users", headers=headers)
    assert resp.status_code == 200, resp.text
    emails = {row["email"] for row in resp.json()}
    assert "accounts_admin@saturdays.com" in emails
    assert "door_staff@saturdays.com" in emails
    assert "resto_owner@saturdays.com" in emails
    owner = next(
        row for row in resp.json() if row["email"] == "resto_owner@saturdays.com"
    )
    assert owner["role"] == "MerchantOwner"
    assert owner["merchant_name"] == "Accounts Cafe"


@pytest.mark.asyncio
async def test_platform_admin_create_edit_deactivate_and_login_block(
    client: AsyncClient, staff_accounts_setup: dict
):
    headers = await _admin_headers(client)
    created = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "New.Admin@Saturdays.com",
            "password": "DoorPass123!",
            "role": "Admin",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert "access_token" not in body
    assert body["email"] == "new.admin@saturdays.com"
    assert body["role"] == "Admin"
    user_id = body["id"]

    login_ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "new.admin@saturdays.com", "password": "DoorPass123!"},
    )
    assert login_ok.status_code == 200

    patched = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={
            "email": "door.reset@saturdays.com",
            "password": "ResetPass123!",
            "is_active": False,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["email"] == "door.reset@saturdays.com"
    assert patched.json()["is_active"] is False

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "door.reset@saturdays.com", "password": "ResetPass123!"},
    )
    assert blocked.status_code == 401
    assert blocked.json()["error_code"] == "USER_INACTIVE"

    audit = await client.get("/api/v1/admin/audit-logs", headers=headers)
    actions = [row["action"] for row in audit.json()]
    assert "STAFF_USER_CREATED" in actions
    assert "STAFF_USER_UPDATED" in actions


@pytest.mark.asyncio
async def test_admin_role_forbidden_on_staff_user_routes(
    client: AsyncClient, staff_accounts_setup: dict
):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "door_staff@saturdays.com", "password": "Password123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    list_resp = await client.get("/api/v1/admin/users", headers=headers)
    assert list_resp.status_code == 403
    create_resp = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "blocked@saturdays.com",
            "password": "Password123!",
            "role": "Admin",
        },
    )
    assert create_resp.status_code == 403
    patch_resp = await client.patch(
        f"/api/v1/admin/users/{staff_accounts_setup['door'].id}",
        headers=headers,
        json={"is_active": False},
    )
    assert patch_resp.status_code == 403


@pytest.mark.asyncio
async def test_branch_manager_created_via_users_appears_on_branch_managers(
    client: AsyncClient, staff_accounts_setup: dict
):
    headers = await _admin_headers(client)
    branch = staff_accounts_setup["branch"]
    created = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "via.users.mgr@saturdays.com",
            "password": "Password123!",
            "role": "BranchManager",
            "branch_id": str(branch.id),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["branch_name"] == "Accounts Branch"
    assert created.json()["brand_name"] == "Accounts Brand"
    assert created.json()["merchant_name"] == "Accounts Cafe"

    listed = await client.get("/api/v1/admin/branch-managers", headers=headers)
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()}
    assert "via.users.mgr@saturdays.com" in emails


@pytest.mark.asyncio
async def test_last_platform_admin_cannot_be_deactivated(
    client: AsyncClient, staff_accounts_setup: dict
):
    headers = await _admin_headers(client)
    admin_id = staff_accounts_setup["admin"].id
    resp = await client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LAST_PLATFORM_ADMIN"


@pytest.mark.asyncio
async def test_cannot_change_own_role(
    client: AsyncClient, staff_accounts_setup: dict, db_session: AsyncSession
):
    extra = await seed_user_login(
        client,
        db_session,
        email="second_admin@saturdays.com",
        role="PlatformAdmin",
    )
    headers = extra["headers"]
    resp = await client.patch(
        f"/api/v1/admin/users/{extra['user'].id}",
        headers=headers,
        json={"role": "Admin"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "CANNOT_MODIFY_OWN_ROLE"


@pytest.mark.asyncio
async def test_staff_user_get_and_duplicate_email(
    client: AsyncClient, staff_accounts_setup: dict
):
    headers = await _admin_headers(client)
    door_id = staff_accounts_setup["door"].id
    one = await client.get(f"/api/v1/admin/users/{door_id}", headers=headers)
    assert one.status_code == 200
    assert one.json()["email"] == "door_staff@saturdays.com"

    missing = await client.get(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000001",
        headers=headers,
    )
    assert missing.status_code == 404

    dup = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "DOOR_STAFF@saturdays.com",
            "password": "Password123!",
            "role": "Admin",
        },
    )
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "EMAIL_ALREADY_EXISTS"
