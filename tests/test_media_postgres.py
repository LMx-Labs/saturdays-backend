"""Image storage on a real PostgreSQL: migration 0008, bytea round trip, and
simultaneous identical uploads. Skipped when `pgserver` is not installed."""

import asyncio
import base64

import pytest

pytest.importorskip("pgserver")

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import User
from app.core.database import get_db_session
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.media.models import MediaFile
from tests.test_cart_postgres import make_database, pg  # noqa: F401

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
# Every byte value, so any text-encoding mishap on the way in or out shows up.
ALL_BYTES = PNG + bytes(range(256)) * 200


async def test_roundtrip_and_concurrent_duplicate_uploads(pg):  # noqa: F811
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
                    email="media@x.in",
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
                json={"email": "media@x.in", "password": "Password123!"},
            )
            headers = {
                "Authorization": "Bearer " + login.json()["access_token"],
                "Content-Type": "image/png",
            }

            responses = await asyncio.gather(
                *[
                    client.post("/api/v1/media", content=ALL_BYTES, headers=headers)
                    for _ in range(5)
                ]
            )
            assert [r.status_code for r in responses] == [201] * 5
            assert len({r.json()["id"] for r in responses}) == 1

            got = await client.get(responses[0].json()["path"])
            assert got.status_code == 200
            assert got.content == ALL_BYTES  # byte-for-byte through PostgreSQL bytea

        async with sessions() as s:
            assert (
                await s.execute(select(func.count()).select_from(MediaFile))
            ).scalar() == 1
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
