from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntityCreate(BaseModel):
    name: str
    entity_type: str
    aliases: list[str] = []
    attributes: dict = {}
    locked_attributes: dict = {}
    knowledge_boundary: dict = {}
    description: str | None = None
    confidence: float = 1.0
    source: str = "manual"


class EntityUpdate(BaseModel):
    name: str | None = None
    entity_type: str | None = None
    aliases: list[str] | None = None
    attributes: dict | None = None
    locked_attributes: dict | None = None
    knowledge_boundary: dict | None = None
    description: str | None = None
    confidence: float | None = None
    source: str | None = None


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    entity_type: str
    aliases: list = []
    attributes: dict = {}
    locked_attributes: dict = {}
    knowledge_boundary: dict = {}
    description: str | None = None
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime


class RelationshipCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    attributes: dict = {}
    valid_from_chapter_id: UUID | None = None
    valid_to_chapter_id: UUID | None = None


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    attributes: dict = {}
    valid_from_chapter_id: UUID | None = None
    valid_to_chapter_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
