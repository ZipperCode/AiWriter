"""Tests for Usage API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.main import app
from app.services.usage_service import UsageService


@pytest.mark.asyncio
async def test_get_usage_summary(client: AsyncClient, auth_headers: dict):
    """Test GET /api/usage/summary endpoint."""
    # Get the override get_db dependency from the app
    async def setup_data():
        get_db_override = app.dependency_overrides[get_db]
        async for session in get_db_override():
            svc = UsageService(session)
            await svc.record_usage(
                model="gpt-4",
                input_tokens=100,
                output_tokens=50,
                cost=0.15,
            )
            await svc.record_usage(
                model="gpt-3.5-turbo",
                input_tokens=200,
                output_tokens=100,
                cost=0.10,
            )
            await session.commit()
            break

    await setup_data()

    resp = await client.get("/api/usage/summary", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "total_input_tokens" in data
    assert "total_output_tokens" in data
    assert "total_cost" in data
    assert "total_calls" in data
    assert data["total_calls"] == 2
    assert data["total_input_tokens"] == 300
    assert data["total_output_tokens"] == 150
    assert abs(data["total_cost"] - 0.25) < 0.001


@pytest.mark.asyncio
async def test_get_usage_by_model(client: AsyncClient, auth_headers: dict):
    """Test GET /api/usage/by-model endpoint."""
    # Setup records
    async def setup_data():
        get_db_override = app.dependency_overrides[get_db]
        async for session in get_db_override():
            svc = UsageService(session)
            await svc.record_usage(
                model="gpt-4",
                input_tokens=100,
                output_tokens=50,
                cost=0.15,
            )
            await svc.record_usage(
                model="gpt-3.5-turbo",
                input_tokens=200,
                output_tokens=100,
                cost=0.10,
            )
            await session.commit()
            break

    await setup_data()

    resp = await client.get("/api/usage/by-model", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Find entries
    models = {item["model"]: item for item in data}
    assert "gpt-4" in models
    assert "gpt-3.5-turbo" in models

    gpt4 = models["gpt-4"]
    assert gpt4["total_input_tokens"] == 100
    assert gpt4["total_output_tokens"] == 50
    assert abs(gpt4["total_cost"] - 0.15) < 0.001
    assert gpt4["call_count"] == 1


@pytest.mark.asyncio
async def test_get_usage_by_agent(client: AsyncClient, auth_headers: dict):
    """Test GET /api/usage/by-agent endpoint."""
    # Setup records
    async def setup_data():
        get_db_override = app.dependency_overrides[get_db]
        async for session in get_db_override():
            svc = UsageService(session)
            await svc.record_usage(
                model="gpt-4",
                input_tokens=100,
                output_tokens=50,
                cost=0.15,
                agent_name="writer",
            )
            await svc.record_usage(
                model="gpt-3.5-turbo",
                input_tokens=200,
                output_tokens=100,
                cost=0.10,
                agent_name="auditor",
            )
            await session.commit()
            break

    await setup_data()

    resp = await client.get("/api/usage/by-agent", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Find entries
    agents = {item["agent_name"]: item for item in data}
    assert "writer" in agents
    assert "auditor" in agents

    writer = agents["writer"]
    assert writer["total_input_tokens"] == 100
    assert writer["total_output_tokens"] == 50
    assert abs(writer["total_cost"] - 0.15) < 0.001
    assert writer["call_count"] == 1


@pytest.mark.asyncio
async def test_usage_summary_requires_auth(client: AsyncClient):
    """Test that summary endpoint requires authentication."""
    resp = await client.get("/api/usage/summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_usage_by_model_requires_auth(client: AsyncClient):
    """Test that by-model endpoint requires authentication."""
    resp = await client.get("/api/usage/by-model")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_usage_by_agent_requires_auth(client: AsyncClient):
    """Test that by-agent endpoint requires authentication."""
    resp = await client.get("/api/usage/by-agent")
    assert resp.status_code in (401, 403)


