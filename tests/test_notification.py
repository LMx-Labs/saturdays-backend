import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.security import hash_password
from app.notification.providers import MockEmailProvider, SendGridEmailProvider


@pytest.fixture
async def setup_notif_user(db_session: AsyncSession):
    user = User(
        email="notif_user@saturdays.com",
        password_hash=hash_password("Password123!"),
        role="Customer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def get_headers(client: AsyncClient, email: str) -> dict:
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_provider_abstraction():
    mock_provider = MockEmailProvider()
    msg_id = await mock_provider.send_email(
        recipient="user@test.com", subject="Test", body="Body content"
    )
    assert msg_id.startswith("mock_msg_")

    sendgrid_provider = SendGridEmailProvider(api_key=None)
    sg_msg_id = await sendgrid_provider.send_email(
        recipient="user@test.com", subject="Test", body="Body content"
    )
    assert sg_msg_id.startswith("sendgrid_mock_")


@pytest.mark.asyncio
async def test_send_and_list_notifications(client: AsyncClient, setup_notif_user: User):
    user = setup_notif_user
    headers = await get_headers(client, user.email)

    send_payload = {
        "recipient": user.email,
        "subject": "Order #ORD-1001 Confirmed",
        "body": "Your order has been placed successfully.",
        "channel": "EMAIL",
    }

    send_resp = await client.post(
        "/api/v1/notifications/send", headers=headers, json=send_payload
    )
    assert send_resp.status_code == 202
    data = send_resp.json()
    assert data["status"] == "SENT"
    assert data["recipient"] == user.email
    assert data["vendor_message_id"] is not None

    list_resp = await client.get("/api/v1/notifications/me", headers=headers)
    assert list_resp.status_code == 200
    notifs = list_resp.json()
    assert len(notifs) >= 1
    assert notifs[0]["subject"] == "Order #ORD-1001 Confirmed"
