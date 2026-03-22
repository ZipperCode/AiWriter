from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VolumeCreate(BaseModel):
    title: str
    objective: str
    climax_hint: str | None = None
    sort_order: int = 1


class VolumeUpdate(BaseModel):
    title: str | None = None
    objective: str | None = None
    climax_hint: str | None = None
    sort_order: int | None = None


class VolumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    objective: str
    climax_hint: str | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime
