"""Schemas for pacing controller."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ChapterPacingResponse(BaseModel):
    chapter_id: UUID
    sort_order: int
    quest_ratio: float
    fire_ratio: float
    constellation_ratio: float
    highlight_count: int
    highlight_types: list[str]
    tension_level: float
    strand_tags: list[str]


class RedLineViolationResponse(BaseModel):
    rule: str
    message: str
    severity: str
    affected_chapters: list[int] = []


class PacingAnalysisResponse(BaseModel):
    chapter_pacing: list[ChapterPacingResponse]
    avg_quest_ratio: float
    avg_fire_ratio: float
    avg_constellation_ratio: float
    total_highlights: int
    avg_tension: float
    violations: list[RedLineViolationResponse] = []


class PacingSuggestionResponse(BaseModel):
    recommended_strands: list[str]
    recommended_highlights: list[str]
    tension_suggestion: str
    target_ratios: dict[str, float]
