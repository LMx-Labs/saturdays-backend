import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.uuidv7 import uuid7
from app.core.exceptions import DomainInvariantError

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": settings.VERSION}

@pytest.mark.asyncio
async def test_liveness_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

@pytest.mark.asyncio
async def test_correlation_id_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
