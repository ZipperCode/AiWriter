import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.state_manager import StateManager
from app.models.project import Project
from app.models.truth_file import TruthFile, TruthFileHistory


async def _create_project(db: AsyncSession) -> Project:
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    tf = TruthFile(project_id=project.id, file_type="current_state", content={"chapter": 0, "characters": []}, version=1)
    db.add(tf)
    await db.flush()
    return project


async def test_get_truth_file(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)
    tf = await mgr.get_truth_file(project.id, "current_state")
    assert tf is not None
    assert tf.file_type == "current_state"
    assert tf.version == 1


async def test_get_truth_file_not_found(db_session: AsyncSession):
    mgr = StateManager(db_session)
    tf = await mgr.get_truth_file(uuid4(), "current_state")
    assert tf is None


async def test_update_truth_file(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)
    # Pass None for chapter_id to avoid FK constraint (no real chapter in test)
    updated = await mgr.update_truth_file(project.id, "current_state", diff={"chapter": 1, "characters": ["Hero"]}, chapter_id=None)
    assert updated.version == 2
    assert updated.content["chapter"] == 1
    assert updated.content["characters"] == ["Hero"]


async def test_update_creates_history(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)
    await mgr.update_truth_file(project.id, "current_state", diff={"chapter": 1}, chapter_id=None)
    history = await mgr.get_history(project.id, "current_state")
    assert len(history) == 1
    assert history[0].version == 1
    assert history[0].content == {"chapter": 0, "characters": []}


async def test_get_truth_file_at_version(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)
    await mgr.update_truth_file(project.id, "current_state", diff={"chapter": 1}, chapter_id=None)
    await mgr.update_truth_file(project.id, "current_state", diff={"chapter": 2}, chapter_id=None)
    v1 = await mgr.get_truth_file_at_version(project.id, "current_state", 1)
    assert v1 is not None
    assert v1.content == {"chapter": 0, "characters": []}
    v2 = await mgr.get_truth_file_at_version(project.id, "current_state", 2)
    assert v2 is not None
    assert v2.content == {"chapter": 1}


async def test_list_truth_files(db_session: AsyncSession):
    project = await _create_project(db_session)
    tf2 = TruthFile(project_id=project.id, file_type="story_bible", content={}, version=1)
    db_session.add(tf2)
    await db_session.flush()
    mgr = StateManager(db_session)
    files = await mgr.list_truth_files(project.id)
    assert len(files) == 2
    types = {f.file_type for f in files}
    assert types == {"current_state", "story_bible"}
