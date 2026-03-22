import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.api.deps import get_db, verify_token
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity


async def _setup_search_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(project_id=project.id, volume_id=vol.id, title="Ch1", sort_order=1, status="draft")
    db.add(ch)
    await db.flush()
    e = Entity(project_id=project.id, name="叶辰", entity_type="character", description="主角", confidence=1.0, source="manual", embedding=[0.5] * 1536)
    db.add(e)
    await db.flush()
    return project, ch, e


async def test_search_endpoint(db_session: AsyncSession):
    project, ch, e = await _setup_search_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        with patch("app.api.search.provider_registry") as mock_registry:
            mock_provider = AsyncMock()
            mock_registry.get_default.return_value = mock_provider

            with patch("app.api.search.HybridRAGEngine") as MockRAG:
                mock_rag = AsyncMock()
                mock_rag.retrieve = AsyncMock(return_value=[])
                MockRAG.return_value = mock_rag

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/search", json={"query": "叶辰", "project_id": str(project.id)})
                assert resp.status_code == 200
                data = resp.json()
                assert "results" in data
                assert "total" in data
    finally:
        app.dependency_overrides.clear()


async def test_search_empty_query(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/search", json={"query": "", "project_id": str(uuid4())})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_search_with_pov(db_session: AsyncSession):
    project, ch, e = await _setup_search_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        with patch("app.api.search.provider_registry") as mock_registry:
            mock_provider = AsyncMock()
            mock_registry.get_default.return_value = mock_provider

            with patch("app.api.search.HybridRAGEngine") as MockRAG:
                mock_rag = AsyncMock()
                mock_rag.retrieve = AsyncMock(return_value=[])
                MockRAG.return_value = mock_rag

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/search", json={"query": "叶辰", "project_id": str(project.id), "pov_entity_id": str(e.id)})
                assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


async def test_search_unknown_project(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        with patch("app.api.search.provider_registry") as mock_registry:
            mock_provider = AsyncMock()
            mock_registry.get_default.return_value = mock_provider

            with patch("app.api.search.HybridRAGEngine") as MockRAG:
                mock_rag = AsyncMock()
                mock_rag.retrieve = AsyncMock(return_value=[])
                MockRAG.return_value = mock_rag

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post("/api/search", json={"query": "test", "project_id": str(uuid4())})
                assert resp.status_code == 200
                assert resp.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()
