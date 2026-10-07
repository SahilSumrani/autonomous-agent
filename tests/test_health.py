import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch
from services.api.app.main import app


@pytest.mark.asyncio
async def test_root_health_endpoint_healthy():
    transport = ASGITransport(app=app)
    with patch("services.api.app.api.v1.routes.health.check_database_health", return_value=True), \
         patch("services.api.app.api.v1.routes.health.check_redis_health", return_value=True):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"]["status"] == "connected"
            assert data["redis"]["status"] == "connected"
            assert "X-Request-ID" in response.headers
            assert "X-Process-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_api_v1_health_endpoint_degraded():
    transport = ASGITransport(app=app)
    with patch("services.api.app.api.v1.routes.health.check_database_health", return_value=False), \
         patch("services.api.app.api.v1.routes.health.check_redis_health", return_value=True):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"]["status"] == "disconnected"
            assert data["redis"]["status"] == "connected"


@pytest.mark.asyncio
async def test_request_id_propagation():
    transport = ASGITransport(app=app)
    custom_request_id = "test-req-12345"
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": custom_request_id})
        assert response.headers.get("X-Request-ID") == custom_request_id
