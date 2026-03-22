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


async def _setup_context_data(db: AsyncSession):
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="Volume 1", objective="Test objective", sort_order=1)
    db.add(volume)
    await db.flush()
    pov = Entity(project_id=project.id, name="叶辰", entity_type="character", knowledge_boundary={"known_events": ["arrived_at_sect"]}, confidence=1.0, source="manual")
    secret_char = Entity(project_id=project.id, name="暗影", entity_type="character", knowledge_boundary={"secret": "is_the_spy"}, confidence=1.0, source="manual")
    db.add_all([pov, secret_char])
    await db.flush()
    ch1 = Chapter(project_id=project.id, volume_id=volume.id, title="Chapter 1", sort_order=1, pov_character_id=pov.id, status="final", summary="叶辰来到青云宗。")
    db.add(ch1)
    await db.flush()
    ch2 = Chapter(project_id=project.id, volume_id=volume.id, title="Chapter 2", sort_order=2, pov_character_id=pov.id, status="planned")
    db.add(ch2)
    await db.flush()
    sc = SceneCard(chapter_id=ch2.id, sort_order=1, pov_character_id=pov.id, location="青云宗大殿", goal="参加入门测试", conflict="测试中遇到强敌")
    db.add(sc)
    tf_state = TruthFile(project_id=project.id, file_type="current_state", content={"last_chapter": 1, "day": 2}, version=1)
    tf_bible = TruthFile(project_id=project.id, file_type="story_bible", content={"world": "修仙世界", "power_system": "灵力"}, version=1)
    db.add_all([tf_state, tf_bible])
    await db.flush()
    return project, volume, pov, ch1, ch2


async def test_assemble_context(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    assert "system_prompt" in ctx
    assert "user_prompt" in ctx
    assert ctx["context_tokens"] > 0
    assert "修仙世界" in ctx["sections"]["story_bible"]
    assert "叶辰来到青云宗" in ctx["sections"]["chapter_summaries"]
    assert "参加入门测试" in ctx["sections"]["scene_cards"]


async def test_pov_filtering(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov.id)
    sections_text = str(ctx["sections"])
    assert "is_the_spy" not in sections_text


async def test_assemble_context_no_pov(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(ch2.id, pov_character_id=None)
    assert ctx["context_tokens"] > 0


async def test_assemble_context_chapter_not_found(db_session: AsyncSession):
    cf = ContextFilter(db_session)
    with pytest.raises(ValueError, match="Chapter .* not found"):
        await cf.assemble_context(uuid4(), None)
