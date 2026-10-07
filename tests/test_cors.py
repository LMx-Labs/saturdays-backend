import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, settings
from app.main import app


def test_cors_origins_parse_comma_separated():
    s = Settings(CORS_ORIGINS="https://a.example.com/, https://b.example.com")
    assert s.CORS_ORIGINS == ["https://a.example.com", "https://b.example.com"]


def test_cors_wildcard_never_combined_with_credentials():
    s = Settings(CORS_ORIGINS="*", CORS_ALLOW_CREDENTIALS=True)
    assert s.cors_allow_credentials_effective is False


@pytest.mark.asyncio
async def test_preflight_allowed_origin():
    origin = settings.CORS_ORIGINS[0]
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin
    assert resp.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_preflight_disallowed_origin_rejected():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_unhandled_500_still_carries_cors_headers():
    """Regression: a 500 used to bypass CORS, so browsers reported a CORS error."""

    @app.get("/__boom")
    async def boom():
        raise RuntimeError("boom")

    origin = settings.CORS_ORIGINS[0]
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/__boom", headers={"Origin": origin})
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/__boom"
        ]

    assert resp.status_code == 500
    assert resp.headers["access-control-allow-origin"] == origin
    assert resp.json()["error_code"] == "INTERNAL_SERVER_ERROR"
    assert resp.headers["x-correlation-id"]
