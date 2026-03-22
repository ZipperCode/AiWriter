"""Schemas for truth file API endpoints."""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TruthFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    file_type: str
    content: dict[str, Any]
    version: int
    created_at: datetime


class TruthFileHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    truth_file_id: UUID
    version: int
    content: dict[str, Any]
    changed_by_chapter_id: UUID | None = None
    created_at: datetime
