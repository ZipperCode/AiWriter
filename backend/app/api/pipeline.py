"""Pipeline API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_token
from app.schemas.pipeline import JobRunResponse, PipelineRunRequest
from app.schemas.human_loop import HumanLoopApproval
from app.services.pipeline_service import PipelineService
from app.orchestration.human_loop import HumanLoopManager, HumanLoopDecision

# Global human loop manager (in production, use Redis-backed storage)
human_loop_manager = HumanLoopManager()

router = APIRouter(prefix="/api", tags=["pipeline"], dependencies=[Depends(verify_token)])


@router.post("/projects/{project_id}/pipeline/write-chapter", response_model=JobRunResponse, status_code=202)
async def start_write_chapter(project_id: UUID, body: PipelineRunRequest, db: AsyncSession = Depends(get_db)):
    svc = PipelineService(db)
    job = await svc.create_job_run(project_id, "pipeline_write")
    return job


@router.get("/pipeline/jobs/{job_id}", response_model=JobRunResponse)
async def get_job_status(job_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = PipelineService(db)
    job = await svc.get_job_run(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/pipeline/jobs/{job_id}/cancel", response_model=JobRunResponse)
async def cancel_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = PipelineService(db)
    job = await svc.get_job_run(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Job already finished")
    updated = await svc.update_job_status(job_id, "cancelled")
    return updated


@router.post("/pipeline/human-loop/{loop_id}/approve", response_model=dict)
async def approve_human_loop(loop_id: UUID, request: HumanLoopApproval):
    """Submit a human decision for a pipeline breakpoint."""
    if not human_loop_manager.is_pending(loop_id):
        raise HTTPException(status_code=404, detail="No pending loop found")
    human_loop_manager.submit_decision(
        loop_id,
        HumanLoopDecision(action=request.action, content=request.content),
    )
    return {"status": "ok", "action": request.action}
