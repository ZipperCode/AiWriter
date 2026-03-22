"""Truth File API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, verify_token
from app.engines.state_manager import StateManager
from app.schemas.truth_file import TruthFileHistoryResponse, TruthFileResponse

router = APIRouter(prefix="/api", tags=["truth-files"], dependencies=[Depends(verify_token)])


@router.get("/projects/{project_id}/truth-files", response_model=list[TruthFileResponse])
async def list_truth_files(project_id: UUID, db: AsyncSession = Depends(get_db)):
    mgr = StateManager(db)
    return await mgr.list_truth_files(project_id)


@router.get("/projects/{project_id}/truth-files/{file_type}", response_model=TruthFileResponse)
async def get_truth_file(project_id: UUID, file_type: str, db: AsyncSession = Depends(get_db)):
    mgr = StateManager(db)
    tf = await mgr.get_truth_file(project_id, file_type)
    if tf is None:
        raise HTTPException(status_code=404, detail=f"Truth file '{file_type}' not found")
    return tf


@router.get("/projects/{project_id}/truth-files/{file_type}/history", response_model=list[TruthFileHistoryResponse])
async def get_truth_file_history(project_id: UUID, file_type: str, db: AsyncSession = Depends(get_db)):
    mgr = StateManager(db)
    return await mgr.get_history(project_id, file_type)
