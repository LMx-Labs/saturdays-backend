"""Deleting a dish, on a real PostgreSQL with one session per request (like production)."""

import asyncio

import pytest

pytest.importorskip("pgserver")

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db_session
from app.main import app as fastapi_app
from tests.test_cart_postgres import make_database, pg, seed_menu  # noqa: F401


async def test_deleted_dish_disappears_from_the_menu_and_carts(pg):  # noqa: F811
    url = await asyncio.to_thread(make_database, pg, "head")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def per_request_session():
        async with sessions() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = per_request_session
    try:
        ids = await seed_menu(sessions)
        transport = httpx.ASGITransport(app=fastapi_app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:

            async def login(email):
                res = await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "Password123!"},
                )
                return {"Authorization": "Bearer " + res.json()["access_token"]}

            owner, customer = await login("o@x.in"), await login("c@x.in")
            branch, item = ids["branch"], ids["item"]

            await client.post(
                "/api/v1/cart/items",
                headers=customer,
                json={"branch_id": branch, "menu_item_id": item, "quantity": 2},
            )
            before = (await client.get(f"/api/v1/branches/{branch}/menu")).json()
            assert [i["name"] for c in before["categories"] for i in c["items"]] == [
                "Chicken Biryani"
            ]

            assert (
                await client.delete(f"/api/v1/menu/items/{item}", headers=owner)
            ).status_code == 204

            after = (await client.get(f"/api/v1/branches/{branch}/menu")).json()
            assert [i for c in after["categories"] for i in c["items"]] == []
            assert (await client.get("/api/v1/cart", headers=customer)).json()[
                "items"
            ] == []
            assert (
                await client.delete(f"/api/v1/menu/items/{item}", headers=owner)
            ).status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
