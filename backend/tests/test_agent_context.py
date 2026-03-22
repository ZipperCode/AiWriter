from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.context_agent import ContextAgent
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.project import Project
from app.models.scene_card import SceneCard
from app.models.truth_file import TruthFile
from app.models.volume import Volume
from app.schemas.agent import AgentContext


async def _setup_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="V1", objective="Test", sort_order=1)
    db.add(volume)
    await db.flush()
    pov = Entity(project_id=project.id, name="Hero", entity_type="character", confidence=1.0, source="manual")
    db.add(pov)
    await db.flush()
    ch = Chapter(project_id=project.id, volume_id=volume.id, title="Ch1", sort_order=1, pov_character_id=pov.id, status="planned")
    db.add(ch)
    await db.flush()
    sc = SceneCard(chapter_id=ch.id, sort_order=1, goal="Test goal", conflict="Test conflict")
    tf = TruthFile(project_id=project.id, file_type="story_bible", content={"setting": "fantasy"}, version=1)
    db.add_all([sc, tf])
    await db.flush()
    return project, ch, pov


async def test_context_agent_execute(db_session: AsyncSession):
    project, ch, pov = await _setup_data(db_session)
    agent = ContextAgent().set_db(db_session)
    ctx = AgentContext(project_id=project.id, chapter_id=ch.id, params={"pov_character_id": str(pov.id)})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.agent_name == "context"
    assert "system_prompt" in result.data
    assert result.data["context_tokens"] > 0


async def test_context_agent_no_chapter(db_session: AsyncSession):
    agent = ContextAgent().set_db(db_session)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is False
    assert "not found" in result.error.lower()


async def test_context_agent_without_pov(db_session: AsyncSession):
    project, ch, _ = await _setup_data(db_session)
    agent = ContextAgent().set_db(db_session)
    ctx = AgentContext(project_id=project.id, chapter_id=ch.id)
    result = await agent.execute(ctx)
    assert result.success is True


async def test_context_agent_no_db():
    agent = ContextAgent()
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is False
    assert "db session" in result.error.lower()
