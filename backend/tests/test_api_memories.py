import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.api.deps import get_db, verify_token
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry


async def _setup_mem_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(project_id=project.id, volume_id=vol.id, title="Ch1", sort_order=1, status="draft")
    db.add(ch)
    await db.flush()
    return project, ch


async def test_create_memory(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        with patch("app.api.memories.provider_registry") as mock_registry:
            mock_provider = AsyncMock()
            mock_registry.get_default.return_value = mock_provider

            with patch("app.api.memories.MemoryEngine") as MockEngine:
                mock_engine = AsyncMock()
                mock_mem = MemoryEntry(chapter_id=ch.id, summary="叶辰来到青云宗")
                db_session.add(mock_mem)
                await db_session.flush()
                mock_engine.create_memory = AsyncMock(return_value=mock_mem)
                MockEngine.return_value = mock_engine
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(f"/api/chapters/{ch.id}/memories", json={"summary": "叶辰来到青云宗"})
                assert resp.status_code == 201
    finally:
        app.dependency_overrides.clear()


async def test_list_memories(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    mem = MemoryEntry(chapter_id=ch.id, summary="Test memory")
    db_session.add(mem)
    await db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/chapters/{ch.id}/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
    finally:
        app.dependency_overrides.clear()


async def test_list_memories_empty(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/chapters/{ch.id}/memories")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()


async def test_create_memory_chapter_not_found(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: "test-token"
    try:
        with patch("app.api.memories.provider_registry") as mock_registry:
            mock_provider = AsyncMock()
            mock_registry.get_default.return_value = mock_provider

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/api/chapters/{uuid4()}/memories", json={"summary": "test"})
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
