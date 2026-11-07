"""A customer's choice about WhatsApp updates: the tick-box behind it, and what it guarantees."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.customer.models import CustomerProfile
from tests.conftest import seed_user_login

ME = "/api/v1/customers/me"


async def _customer(
    client: AsyncClient, db: AsyncSession, email: str = "consent@saturdays.com"
) -> dict:
    user = await seed_user_login(client, db, email)
    return user["headers"]


async def _profile(
    db: AsyncSession, headers_user_email: str = "consent@saturdays.com"
) -> CustomerProfile:
    from sqlalchemy import select

    from app.auth.models import User

    user = (
        await db.execute(select(User).where(User.email == headers_user_email))
    ).scalar_one()
    profile = (
        await db.execute(
            select(CustomerProfile).where(CustomerProfile.user_id == user.id)
        )
    ).scalar_one()
    await db.refresh(profile)
    return profile


async def test_whatsapp_is_off_until_the_customer_turns_it_on(client, db_session):
    headers = await _customer(client, db_session)
    body = (await client.get(ME, headers=headers)).json()
    assert body["whatsapp_opt_in"] is False


async def test_turning_it_on_saves_the_number_in_the_form_whatsapp_needs(
    client, db_session
):
    headers = await _customer(client, db_session)
    res = await client.put(
        ME,
        json={"phone_number": "98765 43210", "whatsapp_opt_in": True},
        headers=headers,
    )
    assert res.status_code == 200 and res.json()["whatsapp_opt_in"] is True
    profile = await _profile(db_session)
    assert profile.whatsapp_opt_in is True and profile.whatsapp_phone == "919876543210"
    assert profile.whatsapp_opt_in_at is not None
    assert profile.phone_number == "98765 43210"  # what they typed is left as typed


async def test_it_can_be_turned_on_later_using_the_number_already_saved(
    client, db_session
):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"full_name": "Asha", "phone_number": "+91 98765 43210"},
        headers=headers,
    )
    assert (
        await _profile(db_session)
    ).whatsapp_opt_in is False  # giving a number is not consent
    res = await client.put(ME, json={"whatsapp_opt_in": True}, headers=headers)
    assert res.status_code == 200
    assert (await _profile(db_session)).whatsapp_phone == "919876543210"


async def test_it_cannot_be_turned_on_without_a_usable_number(client, db_session):
    headers = await _customer(client, db_session)
    res = await client.put(ME, json={"whatsapp_opt_in": True}, headers=headers)
    assert (
        res.status_code == 422 and res.json()["error_code"] == "WHATSAPP_PHONE_INVALID"
    )
    assert "mobile number" in res.json()["message"]
    assert (await client.get(ME, headers=headers)).json()["whatsapp_opt_in"] is False


@pytest.mark.parametrize("bad", ["12345", "abc", "04162223344", "98765"])
async def test_a_mistyped_number_is_caught_when_turning_it_on(client, db_session, bad):
    headers = await _customer(client, db_session)
    res = await client.put(
        ME, json={"phone_number": bad, "whatsapp_opt_in": True}, headers=headers
    )
    assert (
        res.status_code == 422 and res.json()["error_code"] == "WHATSAPP_PHONE_INVALID"
    )
    assert (await client.get(ME, headers=headers)).json()["whatsapp_opt_in"] is False


async def test_turning_it_off_stops_everything(client, db_session):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"phone_number": "9876543210", "whatsapp_opt_in": True},
        headers=headers,
    )
    res = await client.put(ME, json={"whatsapp_opt_in": False}, headers=headers)
    assert res.json()["whatsapp_opt_in"] is False
    profile = await _profile(db_session)
    assert profile.whatsapp_opt_in is False and profile.whatsapp_phone is None


async def test_changing_the_phone_number_moves_the_messages_to_the_new_number(
    client, db_session
):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"phone_number": "9876543210", "whatsapp_opt_in": True},
        headers=headers,
    )
    await client.put(ME, json={"phone_number": "9123456789"}, headers=headers)
    profile = await _profile(db_session)
    assert profile.whatsapp_opt_in is True and profile.whatsapp_phone == "919123456789"


async def test_changing_to_a_number_that_cannot_receive_whatsapp_switches_it_off(
    client, db_session
):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"phone_number": "9876543210", "whatsapp_opt_in": True},
        headers=headers,
    )
    res = await client.put(ME, json={"phone_number": "12345"}, headers=headers)
    assert res.status_code == 200 and res.json()["whatsapp_opt_in"] is False
    assert (await _profile(db_session)).whatsapp_phone is None


async def test_editing_other_details_does_not_disturb_the_choice(client, db_session):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"phone_number": "9876543210", "whatsapp_opt_in": True},
        headers=headers,
    )
    await client.put(ME, json={"full_name": "Asha Kumar"}, headers=headers)
    profile = await _profile(db_session)
    assert (
        profile.whatsapp_opt_in is True
        and profile.whatsapp_phone == "919876543210"
        and profile.full_name == "Asha Kumar"
    )


async def test_turning_it_on_twice_keeps_the_original_consent_time(client, db_session):
    headers = await _customer(client, db_session)
    await client.put(
        ME,
        json={"phone_number": "9876543210", "whatsapp_opt_in": True},
        headers=headers,
    )
    first = (await _profile(db_session)).whatsapp_opt_in_at
    await client.put(ME, json={"whatsapp_opt_in": True}, headers=headers)
    assert (await _profile(db_session)).whatsapp_opt_in_at == first


async def test_a_rejected_request_changes_nothing(client, db_session):
    headers = await _customer(client, db_session)
    await client.put(
        ME, json={"full_name": "Before", "phone_number": "9876543210"}, headers=headers
    )
    res = await client.put(
        ME,
        json={"full_name": "After", "phone_number": "999", "whatsapp_opt_in": True},
        headers=headers,
    )
    assert res.status_code == 422
    profile = await _profile(db_session)
    assert profile.whatsapp_opt_in is False
