import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.embedding_service import EmbeddingService
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter


async def _setup_project(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="V1", objective="obj", sort_order=1)
    db.add(volume)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=volume.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()
    return project, ch


async def test_compute_embedding(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    result = await svc.compute_embedding(["test text"])
    assert len(result) == 1
    assert len(result[0]) == 1536
    mock_provider.embedding.assert_called_once_with(["test text"])


async def test_compute_embedding_batch(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536, [0.2] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    result = await svc.compute_embedding(["text1", "text2"])
    assert len(result) == 2


async def test_embed_entity(db_session: AsyncSession):
    project, ch = await _setup_project(db_session)
    entity = Entity(
        project_id=project.id, name="Hero", entity_type="character",
        confidence=1.0, source="manual",
    )
    db_session.add(entity)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_entity(entity)
    assert entity.embedding is not None


async def test_embed_memory_entry(db_session: AsyncSession):
    project, ch = await _setup_project(db_session)
    mem = MemoryEntry(chapter_id=ch.id, summary="Hero found a sword")
    db_session.add(mem)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.3] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_memory_entry(mem)
    assert mem.embedding is not None


async def test_embed_text_for_query(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.7] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    vec = await svc.embed_query("search text")
    assert len(vec) == 1536


async def test_embed_entity_builds_text(db_session: AsyncSession):
    project, ch = await _setup_project(db_session)
    entity = Entity(
        project_id=project.id, name="Dragon Sword", entity_type="item",
        description="A legendary blade", attributes={"power": "fire"},
        confidence=1.0, source="manual",
    )
    db_session.add(entity)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_entity(entity)
    call_args = mock_provider.embedding.call_args[0][0]
    text = call_args[0]
    assert "Dragon Sword" in text
    assert "item" in text
    assert "fire" in text
