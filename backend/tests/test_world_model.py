import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.world_model import WorldModelEngine
from app.models.project import Project
from app.models.entity import Entity


async def _setup_project_with_entities(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    e1 = Entity(project_id=project.id, name="叶辰", aliases=["叶少", "辰哥"], entity_type="character", attributes={"level": "筑基"}, confidence=1.0, source="manual")
    e2 = Entity(project_id=project.id, name="青云宗", aliases=["青云"], entity_type="faction", attributes={}, confidence=1.0, source="manual")
    db.add_all([e1, e2])
    await db.flush()
    return project, e1, e2


async def test_build_automaton(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)
    automaton = await engine.build_automaton(project.id)
    assert "叶辰" in automaton
    assert "叶少" in automaton
    assert "辰哥" in automaton
    assert "青云宗" in automaton
    assert "青云" in automaton


async def test_match_entities(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)
    text = "叶辰来到青云宗大门前，叶少看着高耸的山门。"
    matches = await engine.match_entities(text, project.id)
    matched_names = {m["name"] for m in matches}
    assert "叶辰" in matched_names
    assert "青云宗" in matched_names


async def test_match_entities_with_aliases(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)
    text = "辰哥一步踏入青云修炼之地。"
    matches = await engine.match_entities(text, project.id)
    entity_ids = {m["entity_id"] for m in matches}
    assert e1.id in entity_ids
    assert e2.id in entity_ids


async def test_match_entities_empty_text(db_session: AsyncSession):
    project, _, _ = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)
    matches = await engine.match_entities("", project.id)
    assert matches == []


async def test_extract_new_entities_with_jieba(db_session: AsyncSession):
    project, _, _ = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)
    text = "苏灵儿站在天剑阁的门口，望着远处的万丈深渊。"
    extracted = await engine.extract_entities_jieba(text)
    assert isinstance(extracted, list)
    for item in extracted:
        assert "text" in item
        assert "flag" in item
