"""Schemas for the three-layer rules system."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BookRulesResponse(BaseModel):
    id: UUID
    project_id: UUID
    base_guardrails: dict[str, Any]
    genre_profile: dict[str, Any]
    custom_rules: dict[str, Any]


class BookRulesUpdate(BaseModel):
    base_guardrails: dict[str, Any] | None = None
    genre_profile: dict[str, Any] | None = None
    custom_rules: dict[str, Any] | None = None


class GenreProfileResponse(BaseModel):
    name: str
    zh_name: str
    disabled_dimensions: list[str]
    taboos: list[dict[str, Any]]
    settings: dict[str, Any]


class GenreListResponse(BaseModel):
    genres: list[GenreProfileResponse]


class MergedRulesResponse(BaseModel):
    guardrails: list[dict[str, Any]]
    taboos: list[dict[str, Any]]
    custom_rules: list[dict[str, Any]]
    settings: dict[str, Any]
    disabled_dimensions: list[str]
    prompt_text: str
