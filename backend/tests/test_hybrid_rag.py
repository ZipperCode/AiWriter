"""Tests for HybridRAGEngine with vector search."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
from app.engines.embedding_service import EmbeddingService
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.relationship import Relationship
from app.config import settings


async def _setup_rag_data(db: AsyncSession):
    """Set up test data for RAG searches."""
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()

    e1 = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        description="主角，天才少年", confidence=1.0, source="manual",
        embedding=[0.9] + [0.0] * 1535,
    )
    e2 = Entity(
        project_id=project.id, name="青云宗", entity_type="faction",
        description="修仙门派", confidence=1.0, source="manual",
        embedding=[0.0] + [0.9] + [0.0] * 1534,
    )
    e3 = Entity(
        project_id=project.id, name="Dragon Sword", entity_type="item",
        description="A legendary blade", confidence=1.0, source="manual",
        embedding=[0.0] * 2 + [0.9] + [0.0] * 1533,
    )
    db.add_all([e1, e2, e3])
    await db.flush()

    m1 = MemoryEntry(
        chapter_id=ch.id, summary="叶辰来到青云宗参加入门测试",
        embedding=[0.85] + [0.1] + [0.0] * 1534,
    )
    m2 = MemoryEntry(
        chapter_id=ch.id, summary="叶辰获得神秘传承",
        embedding=[0.8] + [0.0] * 1535,
    )
    db.add_all([m1, m2])
    await db.flush()

    rel = Relationship(
        project_id=project.id, source_entity_id=e1.id, target_entity_id=e2.id,
        relation_type="belongs_to",
    )
    db.add(rel)
    await db.commit()

    return project, ch, e1, e2, e3, m1, m2, rel


def test_search_result_creation():
    """Test SearchResult dataclass creation."""
    sr = SearchResult(
        source="entity", source_id=uuid4(), content="test",
        score=0.9, metadata={"type": "character"},
    )
    assert sr.source == "entity"
    assert sr.score == 0.9


@pytest.mark.asyncio
async def test_vector_search_entities(db_session: AsyncSession):
    """Test vector search returns results sorted by score."""
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    query_embedding = [0.88] + [0.05] + [0.0] * 1534
    results = await rag.vector_search(query_embedding, project.id, top_k=3)
    assert len(results) > 0
    assert results[0].source in ("entity", "memory")
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_vector_search_empty_project(db_session: AsyncSession):
    """Test vector search on empty project returns empty list."""
    project = Project(title="Empty", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.commit()
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.vector_search([0.1] * 1536, project.id, top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_bm25_search(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    results = await rag.bm25_search("叶辰 青云宗", project.id, top_k=5)
    assert len(results) > 0
    contents = " ".join(r.content for r in results)
    assert "叶辰" in contents or "青云宗" in contents


@pytest.mark.asyncio
async def test_bm25_search_no_results(db_session: AsyncSession):
    project = Project(title="Empty", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.bm25_search("不存在的内容", project.id, top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_graph_search(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    results = await rag.graph_search(e1.id, project.id, depth=1)
    assert len(results) > 0
    names = [r.metadata.get("name") for r in results]
    assert "青云宗" in names


@pytest.mark.asyncio
async def test_graph_search_depth_zero(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.graph_search(e1.id, project.id, depth=0)
    assert len(results) == 0


def test_rrf_fusion():
    id1, id2, id3 = uuid4(), uuid4(), uuid4()
    channel_a = [
        SearchResult("entity", id1, "A", 0.9),
        SearchResult("entity", id2, "B", 0.8),
    ]
    channel_b = [
        SearchResult("entity", id2, "B", 5.0),
        SearchResult("entity", id3, "C", 3.0),
    ]
    fused = HybridRAGEngine.rrf_fusion([channel_a, channel_b], k=60)
    assert len(fused) == 3
    id2_result = next(r for r in fused if r.source_id == id2)
    id1_result = next(r for r in fused if r.source_id == id1)
    assert id2_result.score > id1_result.score


@pytest.mark.asyncio
async def test_rerank_with_mock(db_session: AsyncSession):
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    candidates = [
        SearchResult("entity", uuid4(), "叶辰是天才", 0.5),
        SearchResult("memory", uuid4(), "青云宗入门测试", 0.4),
        SearchResult("entity", uuid4(), "Dragon Sword", 0.3),
    ]

    # Create a mock response object
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={
        "results": [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.85},
            {"index": 2, "relevance_score": 0.60},
        ]
    })
    mock_response.raise_for_status = MagicMock()

    # Create a mock client that supports async context manager
    async def mock_post(*args, **kwargs):
        return mock_response

    mock_client_instance = MagicMock()
    mock_client_instance.post = mock_post
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=None)

    with patch.object(settings, "jina_api_key", "test_key"):
        with patch("app.engines.hybrid_rag.httpx.AsyncClient", return_value=mock_client_instance):
            results = await rag.rerank(candidates, "青云宗测试", top_m=2)
            assert len(results) == 2
            assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_rerank_fallback_no_api_key(db_session: AsyncSession):
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    candidates = [
        SearchResult("entity", uuid4(), "A", 0.9),
        SearchResult("entity", uuid4(), "B", 0.8),
    ]
    with patch.object(settings, "jina_api_key", ""):
        results = await rag.rerank(candidates, "query", top_m=1)
        assert len(results) == 1


@pytest.mark.asyncio
async def test_retrieve_full_pipeline(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.88] + [0.05] + [0.0] * 1534]
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    with patch.object(settings, "jina_api_key", ""):
        results = await rag.retrieve(
            query="叶辰的修炼",
            project_id=project.id,
            pov_entity_id=e1.id,
            top_m=3,
        )
    assert len(results) > 0
    assert len(results) <= 3
    for r in results:
        assert r.content
        assert r.score > 0
