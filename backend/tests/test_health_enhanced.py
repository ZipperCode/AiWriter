"""Tests for enhanced health check endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_health_includes_components(client):
    """Health check should include component status."""
    resp = await client.get("/health")
    data = resp.json()
    assert "components" in data
    assert "database" in data["components"]
    assert "redis" in data["components"]


@pytest.mark.asyncio
async def test_health_includes_version(client):
    """Health check should include app version."""
    resp = await client.get("/health")
    data = resp.json()
    assert "version" in data
