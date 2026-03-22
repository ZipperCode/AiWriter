"""Schemas for pipeline API endpoints."""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class PipelineRunRequest(BaseModel):
    chapter_id: UUID
    mode: str = "auto"


class JobRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID | None
    job_type: str
    status: str
    agent_chain: list[str]
    result: dict[str, Any]
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
