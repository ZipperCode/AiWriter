"""Memory-related request/response schemas."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class MemoryCreate(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    summary: str
    has_embedding: bool
    created_at: str | datetime
