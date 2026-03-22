import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.engines.memory_engine import MemoryEngine
from app.engines.embedding_service import EmbeddingService
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry


async def _setup_memory_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch1 = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="final", summary="叶辰来到青云宗",
    )
    ch2 = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch2",
        sort_order=2, status="final", summary="叶辰参加入门测试",
    )
    db.add_all([ch1, ch2])
    await db.flush()
    return project, ch1, ch2


async def test_create_memory(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem = await engine.create_memory(ch1.id, "叶辰来到青云宗参加修炼")
    assert mem.id is not None
    assert mem.summary == "叶辰来到青云宗参加修炼"
    assert mem.embedding is not None


async def test_retrieve_similar(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem1 = await engine.create_memory(ch1.id, "叶辰来到青云宗")
    mock_provider.embedding.return_value = [[0.6] * 1536]
    mem2 = await engine.create_memory(ch2.id, "叶辰参加入门测试")

    # Verify both memories are created
    all_mems = await engine.get_chapter_memories(ch1.id)
    assert len(all_mems) >= 1
    all_mems2 = await engine.get_chapter_memories(ch2.id)
    assert len(all_mems2) >= 1

    mock_provider.embedding.return_value = [[0.55] * 1536]
    results = await engine.retrieve_similar("叶辰的经历", project.id, top_k=5)
    assert len(results) >= 1


async def test_get_chapter_memories(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    await engine.create_memory(ch1.id, "Memory 1")
    await engine.create_memory(ch1.id, "Memory 2")
    mems = await engine.get_chapter_memories(ch1.id)
    assert len(mems) == 2


async def test_create_memories_from_chapter(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem = await engine.create_memory_from_chapter(ch1)
    assert mem is not None
    assert "叶辰来到青云宗" in mem.summary


async def test_create_memory_from_chapter_no_summary(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    ch1.summary = None
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem = await engine.create_memory_from_chapter(ch1)
    assert mem is None
