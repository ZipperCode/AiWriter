from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChapterCreate(BaseModel):
    title: str
    volume_id: UUID | None = None
    sort_order: int = 1
    pov_character_id: UUID | None = None
    timeline_position: str | None = None
    summary: str | None = None


class ChapterUpdate(BaseModel):
    title: str | None = None
    volume_id: UUID | None = None
    sort_order: int | None = None
    pov_character_id: UUID | None = None
    timeline_position: str | None = None
    status: str | None = None
    summary: str | None = None


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    volume_id: UUID | None = None
    title: str
    sort_order: int
    pov_character_id: UUID | None = None
    timeline_position: str | None = None
    status: str
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
