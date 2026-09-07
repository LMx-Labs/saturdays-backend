import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import DEVELOPMENT_SECRET, Settings, settings
from app.core.exceptions import DomainInvariantError
from app.core.uuidv7 import uuid7
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": settings.VERSION}


@pytest.mark.asyncio
async def test_liveness_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_correlation_id_header():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert "x-correlation-id" in response.headers
        assert len(response.headers["x-correlation-id"]) > 0


@pytest.mark.asyncio
async def test_uuid7_generation():
    u = uuid7()
    assert u.version == 7
    assert len(str(u)) == 36


def test_saturdays_exception_properties():
    exc = DomainInvariantError("Test violation")
    assert exc.status_code == 400
    assert exc.error_code == "DOMAIN_INVARIANT_VIOLATION"
    assert exc.message == "Test violation"


def test_production_settings_reject_development_secrets_and_wildcard_cors():
    provider = {
        "PAYMENT_PROVIDER": "razorpay",
        "RAZORPAY_KEY_ID": "rzp_live_key",
        "RAZORPAY_KEY_SECRET": "provider-secret",
        "RAZORPAY_WEBHOOK_SECRET": "webhook-secret",
    }
    with pytest.raises(ValueError, match="Production JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=DEVELOPMENT_SECRET,
            SECRET_KEY="x" * 32,
            CORS_ORIGINS=["https://app.example.com"],
            **provider,
        )

    with pytest.raises(ValueError, match="explicit trusted origins"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="j" * 32,
            SECRET_KEY="s" * 32,
            CORS_ORIGINS=["*"],
            **provider,
        )

    with pytest.raises(ValueError, match="configured provider"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="j" * 32,
            SECRET_KEY="s" * 32,
            INTERNAL_CLEANUP_KEY="c" * 32,
            CORS_ORIGINS=["https://app.example.com"],
        )
