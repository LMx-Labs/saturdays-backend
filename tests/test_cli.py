import pytest
from sqlalchemy import select

from app.cli import CliError, create_user, set_password
from app.merchant.models import Merchant


async def _login(client, email, password):
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


async def test_create_owner_with_merchant_can_log_in(client, db_session):
    user, merchant = await create_user(
        db_session,
        email=" Owner@Diner.in ",
        password="Password123!",
        role="MerchantOwner",
        business_name="Diner",
        legal_name="Diner LLP",
        fssai="12345678901234",
    )
    assert user.email == "owner@diner.in"
    assert merchant is not None and merchant.owner_user_id == user.id

    res = await _login(client, "owner@diner.in", "Password123!")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "MerchantOwner"

    token = res.json()["access_token"]
    me = await client.get(
        "/api/v1/merchants/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["business_name"] == "Diner"


async def test_bootstrap_platform_admin(client, db_session):
    await create_user(
        db_session, email="root@sat.in", password="Password123!", role="PlatformAdmin"
    )
    res = await _login(client, "root@sat.in", "Password123!")
    assert res.status_code == 200
    token = res.json()["access_token"]
    # The new admin can use the admin API to create further logins.
    users = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert users.status_code == 200


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"role": "Customer"}, "Role must be one of"),
        ({"role": "MerchantOwner", "password": "short"}, "at least 8"),
        ({"role": "PlatformAdmin", "fssai": "1"}, "only apply to MerchantOwner"),
        ({"role": "MerchantOwner", "business_name": "Diner"}, "give all of"),
    ],
)
async def test_create_user_rejects_bad_input(db_session, kwargs, message):
    args = {"email": "x@y.in", "password": "Password123!", **kwargs}
    with pytest.raises(CliError, match=message):
        await create_user(db_session, **args)


async def test_duplicate_email_is_rejected_case_insensitively(db_session):
    await create_user(db_session, email="a@b.in", password="Password123!", role="Admin")
    with pytest.raises(CliError, match="already exists"):
        await create_user(
            db_session, email="A@B.IN", password="Password123!", role="Admin"
        )


async def test_set_password_resets_and_reactivates(client, db_session):
    user, _ = await create_user(
        db_session, email="o@d.in", password="Password123!", role="MerchantOwner"
    )
    user.is_active = False
    await db_session.commit()

    await set_password(db_session, email="O@D.in", password="NewPassword456!")
    assert (await _login(client, "o@d.in", "Password123!")).status_code == 401
    assert (await _login(client, "o@d.in", "NewPassword456!")).status_code == 200
    assert (await db_session.execute(select(Merchant))).first() is None


async def test_set_password_unknown_email(db_session):
    with pytest.raises(CliError, match="No user"):
        await set_password(db_session, email="ghost@x.in", password="Password123!")
