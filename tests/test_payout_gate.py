"""Production payout initiation remains closed until real collection is agreed."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.security import create_access_token, hash_password
from app.payout.models import Payout
from app.subscription.models import PlatformCommission


@pytest.mark.asyncio
async def test_admin_cannot_start_or_preview_simulated_payout(
    client: AsyncClient, db_session: AsyncSession
):
    admin = User(
        email="payout-gate-admin@example.com",
        password_hash=hash_password("TestOnlyPassword123!"),
        role="PlatformAdmin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=str(admin.id), role='PlatformAdmin')}"
    }
    for body in ({}, {"dry_run": True}):
        response = await client.post("/api/v1/payouts/run", headers=headers, json=body)
        assert response.status_code == 503
        assert response.json()["error_code"] == "PAYMENT_COLLECTION_UNAVAILABLE"
    assert await db_session.scalar(select(func.count()).select_from(Payout)) == 0
    assert (
        await db_session.scalar(select(func.count()).select_from(PlatformCommission))
        == 0
    )
