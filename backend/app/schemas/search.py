"""Search-related request/response schemas."""

from uuid import UUID
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    project_id: UUID
    pov_entity_id: UUID | None = None
    top_m: int = Field(default=5, ge=1, le=50)


class SearchResultResponse(BaseModel):
    source: str
    source_id: UUID
    content: str
    score: float
    metadata: dict = {}


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total: int
