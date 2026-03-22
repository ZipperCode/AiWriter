# backend/tests/test_context_filter_v2.py
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.context_filter import ContextFilter
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.truth_file import TruthFile
from app.models.scene_card import SceneCard
from app.models.book_rules import BookRules
from app.models.pacing_meta import PacingMeta


async def _setup_full_context(db: AsyncSession):
    """Setup project with book rules and pacing meta."""
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    # Add book rules
    rules = BookRules(
        project_id=project.id,
        base_guardrails={},
        genre_profile={"name": "xuanhuan"},
        custom_rules={"custom_rules": [{"id": "c1", "rule": "No romance subplot"}]},
    )
    db.add(rules)

    volume = Volume(project_id=project.id, title="V1", objective="Test", sort_order=1)
    db.add(volume)
    await db.flush()

    pov = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        knowledge_boundary={"known_events": ["arrived"]}, confidence=1.0, source="manual",
    )
    db.add(pov)
    await db.flush()

    ch1 = Chapter(
        project_id=project.id, volume_id=volume.id, title="Ch1",
        sort_order=1, pov_character_id=pov.id, status="final", summary="叶辰到达。",
    )
    db.add(ch1)
    await db.flush()

    # Pacing meta for ch1
    pm = PacingMeta(
        chapter_id=ch1.id,
        quest_ratio=0.8, fire_ratio=0.1, constellation_ratio=0.1,
        highlight_count=1, highlight_types=["越级反杀"],
        tension_level=0.5, strand_tags=["quest"],
    )
    db.add(pm)

    ch2 = Chapter(
        project_id=project.id, volume_id=volume.id, title="Ch2",
        sort_order=2, pov_character_id=pov.id, status="planned",
    )
    db.add(ch2)
    await db.flush()

    sc = SceneCard(
        chapter_id=ch2.id, sort_order=1, pov_character_id=pov.id,
        location="大殿", goal="测试", conflict="遇到强敌",
    )
    db.add(sc)

    tf = TruthFile(
        project_id=project.id, file_type="story_bible",
        content={"world": "修仙世界"}, version=1,
    )
    db.add(tf)
    await db.flush()

    return project, pov, ch1, ch2


async def test_context_includes_rules(db_session: AsyncSession):
    """Context should include rules section."""
    project, pov, ch1, ch2 = await _setup_full_context(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    system_prompt = ctx["system_prompt"]
    assert "基础护栏" in system_prompt or "规则" in system_prompt


async def test_context_includes_deai(db_session: AsyncSession):
    """Context should include De-AI prohibitions."""
    project, pov, ch1, ch2 = await _setup_full_context(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    system_prompt = ctx["system_prompt"]
    assert "禁止" in system_prompt or "不使用" in system_prompt


async def test_context_includes_pacing(db_session: AsyncSession):
    """Context should include pacing suggestion."""
    project, pov, ch1, ch2 = await _setup_full_context(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    # Pacing suggestion should appear in user prompt or sections
    sections = ctx.get("sections", {})
    has_pacing = "pacing" in sections or "节奏" in ctx.get("user_prompt", "")
    assert has_pacing


async def test_context_sections_have_rules_key(db_session: AsyncSession):
    """Sections dict should have a 'rules' key."""
    project, pov, ch1, ch2 = await _setup_full_context(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    assert "rules" in ctx["sections"]
