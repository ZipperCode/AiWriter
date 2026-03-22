import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.context_filter import ContextFilter
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.truth_file import TruthFile
from app.models.scene_card import SceneCard


async def _setup_rag_context_data(db: AsyncSession):
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="V1", objective="Test", sort_order=1)
    db.add(volume)
    await db.flush()
    pov = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        knowledge_boundary={"known_events": ["arrived"]},
        confidence=1.0, source="manual",
    )
    db.add(pov)
    await db.flush()
    chapters = []
    for i in range(1, 7):
        ch = Chapter(
            project_id=project.id, volume_id=volume.id,
            title=f"Chapter {i}", sort_order=i,
            pov_character_id=pov.id,
            status="final" if i < 6 else "planned",
            summary=f"第{i}章内容摘要",
        )
        db.add(ch)
        await db.flush()
        chapters.append(ch)
    tf_bible = TruthFile(
        project_id=project.id, file_type="story_bible",
        content={"world": "修仙世界"}, version=1,
    )
    tf_state = TruthFile(
        project_id=project.id, file_type="current_state",
        content={"chapter": 5}, version=1,
    )
    db.add_all([tf_bible, tf_state])
    await db.flush()
    sc = SceneCard(
        chapter_id=chapters[-1].id, sort_order=1,
        pov_character_id=pov.id, location="大殿",
        goal="测试", conflict="强敌",
    )
    db.add(sc)
    await db.flush()
    return project, volume, pov, chapters


async def test_context_with_rag_section(db_session: AsyncSession):
    """After chapter 5, context should include RAG results section."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[-1]  # Chapter 6

    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        from app.engines.hybrid_rag import SearchResult
        mock_rag.retrieve.return_value = [
            SearchResult("entity", uuid4(), "RAG result content", 0.9),
        ]
        with patch("app.engines.context_filter.EmbeddingService"):
            with patch("app.engines.context_filter.provider_registry") as mock_reg:
                mock_reg.get_default.return_value = AsyncMock()
                cf = ContextFilter(db_session)
                ctx = await cf.assemble_context(target_ch.id, pov.id)

    assert "rag_results" in ctx["sections"]
    assert "RAG result content" in ctx["sections"]["rag_results"]


async def test_context_without_rag_early_chapters(db_session: AsyncSession):
    """Chapters 1-5 should not use RAG (full context mode)."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[0]  # Chapter 1

    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(target_ch.id, pov.id)
    assert "rag_results" not in ctx.get("sections", {})


async def test_progressive_context_strategy(db_session: AsyncSession):
    """Verify progressive context: ch1-5 = full, ch6+ = progressive."""
    cf = ContextFilter(db_session)
    assert cf._get_context_strategy(1) == "full"
    assert cf._get_context_strategy(5) == "full"
    assert cf._get_context_strategy(6) == "progressive"
    assert cf._get_context_strategy(21) == "progressive"


async def test_context_rag_fallback_on_error(db_session: AsyncSession):
    """If RAG fails, context should still work without RAG section."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[-1]

    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        mock_rag.retrieve.side_effect = Exception("RAG failed")
        with patch("app.engines.context_filter.EmbeddingService"):
            with patch("app.engines.context_filter.provider_registry") as mock_reg:
                mock_reg.get_default.return_value = AsyncMock()
                cf = ContextFilter(db_session)
                ctx = await cf.assemble_context(target_ch.id, pov.id)

    assert ctx["context_tokens"] > 0
    assert "rag_results" not in ctx["sections"]
