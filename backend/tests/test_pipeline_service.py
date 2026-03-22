from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.pipeline_service import PipelineService


async def _create_project(db: AsyncSession) -> Project:
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    return project


async def test_create_job_run(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "pipeline_write")
    assert job.project_id == project.id
    assert job.job_type == "pipeline_write"
    assert job.status == "pending"


async def test_update_job_status(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "pipeline_write")
    updated = await svc.update_job_status(job.id, "running")
    assert updated.status == "running"
    updated = await svc.update_job_status(job.id, "completed")
    assert updated.status == "completed"


async def test_get_job_run(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "pipeline_write")
    found = await svc.get_job_run(job.id)
    assert found is not None
    assert found.id == job.id


async def test_get_job_run_not_found(db_session: AsyncSession):
    svc = PipelineService(db_session)
    found = await svc.get_job_run(uuid4())
    assert found is None


async def test_update_job_with_result(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "audit")
    updated = await svc.update_job_status(
        job.id,
        "completed",
        result={"pass_rate": 0.95},
        agent_chain=["radar", "auditor"],
    )
    assert updated.result == {"pass_rate": 0.95}
    assert updated.agent_chain == ["radar", "auditor"]
