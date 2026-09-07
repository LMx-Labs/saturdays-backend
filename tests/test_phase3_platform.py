import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_phase3_admin_and_tenant_routes_require_authentication(client: AsyncClient):
    protected = [
        "/api/v1/admin/merchants",
        "/api/v1/payments/history",
        f"/api/v1/inventory/{uuid.uuid4()}",
        f"/api/v1/reports/branches/{uuid.uuid4()}/performance",
        "/api/v1/reports/platform/operations",
    ]
    for path in protected:
        response = await client.get(path)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_cannot_use_admin_or_merchant_mutations(
    client: AsyncClient, provision_headers
):
    headers = await provision_headers("phase3-customer@example.com", "Customer")
    assert (await client.get("/api/v1/admin/merchants", headers=headers)).status_code == 403
    assert (
        await client.post(
            "/api/v1/coupons",
            headers=headers,
            json={
                "code": "BLOCKED",
                "discount_type": "FLAT",
                "discount_value": 10,
                "valid_from": "2026-09-01T00:00:00Z",
                "valid_until": "2026-09-30T00:00:00Z",
            },
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_notification_preferences_are_user_scoped(client: AsyncClient, provision_headers):
    headers = await provision_headers("phase3-preferences@example.com", "Customer")
    initial = await client.get("/api/v1/notifications/me/preferences", headers=headers)
    assert initial.status_code == 200
    updated = await client.put(
        "/api/v1/notifications/me/preferences",
        headers=headers,
        json={
            "email_enabled": False,
            "sms_enabled": True,
            "push_enabled": True,
            "order_updates": True,
            "marketing": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["email_enabled"] is False
    assert updated.json()["sms_enabled"] is True
