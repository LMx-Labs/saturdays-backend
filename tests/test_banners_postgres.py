"""Creating, listing and deleting hero banners on a real, migrated PostgreSQL."""

import asyncio

import pytest

pgserver = pytest.importorskip("pgserver")

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import User
from app.core.database import get_db_session
from app.core.security import hash_password
from app.main import app as fastapi_app
from tests.test_cart_postgres import make_database


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield str(data_dir)
    server.cleanup()


async def test_banner_create_list_delete(pg):
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def per_request_session():
        async with sessions() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = per_request_session
    try:
        async with sessions() as s:
            s.add(
                User(
                    email="banners@x.in",
                    password_hash=hash_password("Password123!"),
                    role="PlatformAdmin",
                    is_active=True,
                    is_verified=True,
                )
            )
            await s.commit()

        transport = httpx.ASGITransport(app=fastapi_app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "banners@x.in", "password": "Password123!"},
            )
            admin = {"Authorization": "Bearer " + login.json()["access_token"]}

            created = await client.post(
                "/api/v1/admin/banners",
                headers=admin,
                json={
                    "title": "DIWALI SALE",
                    "image_url": "https://saturdays-v2-main.vercel.app/api/v1/media/01a1affa-80f3-7b94-a687-4c1a2f0f3a11",
                    "target_url": None,
                    "display_order": 1,
                    "is_active": True,
                },
            )
            assert created.status_code in (200, 201), created.text
            banner_id = created.json()["id"]

            listed = await client.get("/api/v1/admin/banners", headers=admin)
            assert [b["title"] for b in listed.json()] == ["DIWALI SALE"]

            gone = await client.delete(
                f"/api/v1/admin/banners/{banner_id}", headers=admin
            )
            assert gone.status_code in (200, 204)
            assert (
                await client.get("/api/v1/admin/banners", headers=admin)
            ).json() == []
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
