"""Embedding computation and storage service."""

import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.draft import Draft
from app.providers.base import BaseLLMProvider


class EmbeddingService:
    """Compute and store embeddings for entities, memories, and drafts."""

    def __init__(self, db: AsyncSession, provider: BaseLLMProvider):
        self.db = db
        self.provider = provider

    async def compute_embedding(self, texts: list[str]) -> list[list[float]]:
        """Compute embeddings for a list of texts."""
        return await self.provider.embedding(texts)

    async def embed_query(self, text: str) -> list[float]:
        """Compute embedding for a single query text."""
        results = await self.compute_embedding([text])
        return results[0]

    async def embed_entity(self, entity: Entity) -> None:
        """Compute and store embedding for an entity."""
        text = self._build_entity_text(entity)
        embeddings = await self.compute_embedding([text])
        entity.embedding = embeddings[0]

    async def embed_memory_entry(self, memory: MemoryEntry) -> None:
        """Compute and store embedding for a memory entry."""
        embeddings = await self.compute_embedding([memory.summary])
        memory.embedding = embeddings[0]

    async def embed_draft(self, draft: Draft) -> None:
        """Compute and store embedding for a draft."""
        text = draft.content[:2000] if draft.content else ""
        if text:
            embeddings = await self.compute_embedding([text])
            draft.content_embedding = embeddings[0]

    @staticmethod
    def _build_entity_text(entity: Entity) -> str:
        """Build a text representation of an entity for embedding."""
        parts = [f"[{entity.entity_type}] {entity.name}"]
        if entity.description:
            parts.append(entity.description)
        if entity.attributes:
            attrs_str = json.dumps(entity.attributes, ensure_ascii=False)
            parts.append(f"attributes: {attrs_str}")
        return " | ".join(parts)
