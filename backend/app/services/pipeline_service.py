"""Pipeline service: manages job runs."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun


class PipelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job_run(self, project_id: UUID, job_type: str) -> JobRun:
        job = JobRun(
            project_id=project_id,
            job_type=job_type,
            status="pending",
            agent_chain=[],
            result={},
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job_run(self, job_id: UUID) -> JobRun | None:
        stmt = select(JobRun).where(JobRun.id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_job_status(
        self,
        job_id: UUID,
        status: str,
        result: dict | None = None,
        error_message: str | None = None,
        agent_chain: list[str] | None = None,
    ) -> JobRun:
        job = await self.get_job_run(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed", "cancelled"):
            job.finished_at = datetime.now(timezone.utc)
        if result is not None:
            job.result = result
        if error_message is not None:
            job.error_message = error_message
        if agent_chain is not None:
            job.agent_chain = agent_chain
        await self.db.flush()
        return job

    async def save_checkpoint(self, job_id: UUID, checkpoint_data: dict) -> JobRun:
        """Save checkpoint data to a job run."""
        job = await self.get_job_run(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.checkpoint_data = checkpoint_data
        await self.db.flush()
        return job

    async def get_checkpoint(self, job_id: UUID) -> dict:
        """Get checkpoint data from a job run."""
        job = await self.get_job_run(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        return job.checkpoint_data or {}
