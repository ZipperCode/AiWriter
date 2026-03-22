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
