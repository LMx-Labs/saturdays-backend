import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.brand.models import Brand
from app.core.security import create_access_token
from app.kitchen.models import Kitchen
from app.menu.models import Menu
from app.merchant.models import Merchant


@pytest.mark.asyncio
async def test_new_branch_has_menu_and_kitchen_and_repair_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
):
    owner = User(
        email="workspace-owner@example.com", role="MerchantOwner", is_active=True
    )
    db_session.add(owner)
    await db_session.flush()
    merchant = Merchant(
        owner_user_id=owner.id,
        business_name="Workspace Merchant",
        legal_entity_name="Workspace Merchant",
        fssai_license_number="12345678901234",
        status="APPROVED",
    )
    db_session.add(merchant)
    await db_session.flush()
    brand = Brand(merchant_id=merchant.id, name="Workspace Brand")
    db_session.add(brand)
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=str(owner.id), role='MerchantOwner')}"
    }
    created = await client.post(
        "/api/v1/branches",
        json={
            "brand_id": str(brand.id),
            "name": "Workspace Branch",
            "address_text": "Test Lane",
        },
        headers=headers,
    )
    assert created.status_code == 201
    branch_id = created.json()["id"]
    branch_uuid = uuid.UUID(branch_id)
    for _ in range(2):
        repaired = await client.post(
            f"/api/v1/branches/{branch_id}/workspace/initialize",
            headers=headers,
        )
        assert repaired.status_code == 200
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Menu).where(Menu.branch_id == branch_uuid)
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Kitchen)
            .where(Kitchen.branch_id == branch_uuid)
        )
        == 1
    )
