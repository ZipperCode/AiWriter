"""Schemas for quality audit system."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditDimensionScore(BaseModel):
    dimension_id: int
    name: str
    zh_name: str
    category: str
    score: float
    severity: str
    message: str
    evidence: list[dict[str, Any]] = []


class AuditReportResponse(BaseModel):
    chapter_id: UUID
    mode: str
    scores: list[AuditDimensionScore]
    pass_rate: float
    has_blocking: bool
    recommendation: str
    issues: list[dict[str, Any]] = []


class DimensionListResponse(BaseModel):
    dimensions: list[dict[str, Any]]
    total: int
    active: int
