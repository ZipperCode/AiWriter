from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    title: str
    genre: str
    description: str | None = None
    settings: dict = {}
    target_words: int | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    genre: str | None = None
    description: str | None = None
    status: str | None = None
    settings: dict | None = None
    target_words: int | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    genre: str
    status: str
    description: str | None = None
    settings: dict = {}
    target_words: int | None = None
    created_at: datetime
    updated_at: datetime
