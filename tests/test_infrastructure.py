import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db_session
from app.core.exceptions import DomainInvariantError
from app.core.uuidv7 import uuid7
from app.main import _validate_production_settings, app


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
async def test_readiness_fails_when_database_is_unavailable():
    class BrokenSession:
        async def execute(self, _statement):
            raise ConnectionError("synthetic database outage")

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[get_db_session] = broken_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health/ready")
        assert response.status_code == 503
        assert "synthetic database outage" not in response.text
    finally:
        app.dependency_overrides.clear()


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


def test_production_startup_without_disabled_payment_secrets(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings, "JWT_SECRET_KEY", "a-unique-production-signing-key-with-32-chars"
    )
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://restaurant.example.test"])
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "")
    monkeypatch.setattr(settings, "RAZORPAYX_ACCOUNT_NUMBER", "")
    monkeypatch.setattr(settings, "PAYOUT_SCHEDULER_ENABLED", False)
    _validate_production_settings()
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", True)
    with pytest.raises(RuntimeError, match="RAZORPAY_SIMULATE"):
        _validate_production_settings()
    monkeypatch.setattr(settings, "RAZORPAY_SIMULATE", False)
    monkeypatch.setattr(settings, "PAYOUT_SCHEDULER_ENABLED", True)
    with pytest.raises(RuntimeError, match="PAYOUT_SCHEDULER_ENABLED"):
        _validate_production_settings()
