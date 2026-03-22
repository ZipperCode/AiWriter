import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.embedding_service import EmbeddingService
from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
from app.engines.memory_engine import MemoryEngine
from app.engines.context_filter import ContextFilter
from app.events.event_bus import EventBus, PipelineEvent
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.truth_file import TruthFile


async def _setup_integration_data(db: AsyncSession):
    project = Project(title="Integration", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()

    pov = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        description="主角", confidence=1.0, source="manual",
        embedding=[0.5] * 1536,
    )
    db.add(pov)
    await db.flush()

    chapters = []
    for i in range(1, 8):
        ch = Chapter(
            project_id=project.id, volume_id=vol.id,
            title=f"Chapter {i}", sort_order=i,
            pov_character_id=pov.id,
            status="final" if i < 7 else "planned",
            summary=f"第{i}章发生了精彩的故事",
        )
        db.add(ch)
        await db.flush()
        chapters.append(ch)

    tf = TruthFile(
        project_id=project.id, file_type="story_bible",
        content={"world": "修仙世界"}, version=1,
    )
    tf2 = TruthFile(
        project_id=project.id, file_type="current_state",
        content={"chapter": 6}, version=1,
    )
    db.add_all([tf, tf2])
    await db.flush()
    return project, pov, chapters


@pytest.mark.asyncio
async def test_rag_to_memory_flow(db_session: AsyncSession):
    """Test: create memories -> embed -> retrieve via RAG."""
    project, pov, chapters = await _setup_integration_data(db_session)

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    mem_engine = MemoryEngine(db_session, embed_svc)

    # Create memories for first 3 chapters
    for ch in chapters[:3]:
        await mem_engine.create_memory(ch.id, ch.summary)

    # Retrieve via RAG
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.vector_search([0.5] * 1536, project.id, top_k=5)
    # Should find entity + memories
    assert len(results) > 0


@pytest.mark.asyncio
async def test_context_filter_with_rag_integration(db_session: AsyncSession):
    """Test progressive context with RAG for late chapters."""
    project, pov, chapters = await _setup_integration_data(db_session)
    target = chapters[-1]  # Chapter 7

    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        mock_rag.retrieve.return_value = [
            SearchResult("entity", uuid4(), "RAG找到了重要线索", 0.9),
        ]
        with patch("app.engines.context_filter.EmbeddingService"):
            with patch("app.engines.context_filter.provider_registry") as mock_reg:
                mock_reg.get_default.return_value = AsyncMock()
                cf = ContextFilter(db_session)
                ctx = await cf.assemble_context(target.id, pov.id)

    assert ctx["context_tokens"] > 0
    assert "rag_results" in ctx["sections"]


@pytest.mark.asyncio
async def test_event_bus_roundtrip():
    """Test event serialization/deserialization roundtrip."""
    job_id = uuid4()
    events = [
        PipelineEvent(job_id, "agent_start", "radar"),
        PipelineEvent(job_id, "agent_complete", "radar", {"duration_ms": 500}),
        PipelineEvent(job_id, "agent_start", "writer"),
        PipelineEvent(job_id, "pipeline_complete", "", {"total_ms": 5000}),
    ]
    for e in events:
        restored = PipelineEvent.from_json(e.to_json())
        assert restored.event_type == e.event_type
        assert restored.agent_name == e.agent_name


@pytest.mark.asyncio
async def test_full_iter4_components_exist():
    """Verify all iteration 4 components are importable."""
    from app.engines.embedding_service import EmbeddingService
    from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
    from app.engines.memory_engine import MemoryEngine
    from app.events.event_bus import EventBus, PipelineEvent
    from app.api.search import router as search_router
    from app.api.memories import router as memories_router
    from app.api.ws import router as ws_router
    from app.schemas.search import SearchRequest, SearchResponse
    from app.schemas.memory import MemoryCreate, MemoryResponse

    assert EmbeddingService is not None
    assert HybridRAGEngine is not None
    assert MemoryEngine is not None
    assert EventBus is not None
