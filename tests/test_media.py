"""Image uploads for restaurant, dish and banner photos."""

import base64

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.service import MAX_UPLOAD_BYTES
from tests.conftest import seed_user_login

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


def _auth(login: dict) -> dict:
    return {"Authorization": f"Bearer {login['access_token']}"}


async def _upload(
    client: AsyncClient, login: dict, body: bytes, content_type="image/png"
):
    return await client.post(
        "/api/v1/media",
        content=body,
        headers={**_auth(login), "Content-Type": content_type},
    )


@pytest.fixture
async def admin(client: AsyncClient, db_session: AsyncSession) -> dict:
    return await seed_user_login(
        client, db_session, "media.admin@saturdays.com", role="PlatformAdmin"
    )


async def test_upload_then_fetch_returns_the_same_bytes(
    client: AsyncClient, admin: dict
):
    res = await _upload(client, admin, PNG)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(PNG)
    assert body["path"] == f"/api/v1/media/{body['id']}"

    # Public: no login needed to display a photo.
    got = await client.get(body["path"])
    assert got.status_code == 200
    assert got.content == PNG
    assert got.headers["content-type"] == "image/png"
    assert "immutable" in got.headers["cache-control"]
    assert got.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "payload, expected",
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")],
)
async def test_type_comes_from_the_bytes_not_the_header(
    client: AsyncClient, admin: dict, payload: bytes, expected: str
):
    res = await _upload(client, admin, payload, content_type="application/octet-stream")
    assert res.status_code == 201
    assert res.json()["content_type"] == expected


async def test_same_image_uploaded_twice_is_stored_once(
    client: AsyncClient, admin: dict
):
    first = (await _upload(client, admin, PNG)).json()
    second = (await _upload(client, admin, PNG)).json()
    assert first["id"] == second["id"]


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"GIF89a" + b"\x00" * 20,
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b"just some text",
        b"MZ\x90\x00" + b"\x00" * 20,
    ],
)
async def test_rejects_anything_that_is_not_png_jpeg_or_webp(
    client: AsyncClient, admin: dict, payload: bytes
):
    res = await _upload(client, admin, payload)
    assert res.status_code == 422
    assert res.json()["error_code"] in {"MEDIA_EMPTY", "MEDIA_UNSUPPORTED_TYPE"}


async def test_rejects_oversized_images(client: AsyncClient, admin: dict):
    res = await _upload(client, admin, PNG + b"\x00" * MAX_UPLOAD_BYTES)
    assert res.status_code == 413
    assert res.json()["error_code"] == "MEDIA_TOO_LARGE"


async def test_requires_login(client: AsyncClient):
    res = await client.post(
        "/api/v1/media", content=PNG, headers={"Content-Type": "image/png"}
    )
    assert res.status_code == 401


@pytest.mark.parametrize(
    "role, allowed",
    [
        ("Customer", False),
        ("KitchenStaff", False),
        ("MerchantOwner", True),
        ("BranchManager", True),
        ("Admin", True),
        ("PlatformAdmin", True),
    ],
)
async def test_only_staff_roles_can_upload(
    client: AsyncClient, db_session: AsyncSession, role: str, allowed: bool
):
    login = await seed_user_login(
        client, db_session, f"media.{role.lower()}@saturdays.com", role=role
    )
    res = await _upload(client, login, PNG)
    assert res.status_code == (201 if allowed else 403)


async def test_conditional_request_gets_304(client: AsyncClient, admin: dict):
    path = (await _upload(client, admin, PNG)).json()["path"]
    first = await client.get(path)
    again = await client.get(path, headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""


async def test_unknown_image_is_404(client: AsyncClient):
    res = await client.get("/api/v1/media/01a19ba4-21aa-79de-98c9-732e4392191d")
    assert res.status_code == 404
    assert res.json()["error_code"] == "MEDIA_NOT_FOUND"
