"""Memory engine: chapter memory creation and similarity retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.embedding_service import EmbeddingService
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry


class MemoryEngine:
    """Manages chapter memories with embedding-based retrieval."""

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embed_svc = embedding_service

    async def create_memory(self, chapter_id: UUID, summary: str) -> MemoryEntry:
        """Create a memory entry with computed embedding."""
        mem = MemoryEntry(chapter_id=chapter_id, summary=summary)
        self.db.add(mem)
        await self.db.flush()
        await self.embed_svc.embed_memory_entry(mem)
        return mem

    async def create_memory_from_chapter(self, chapter: Chapter) -> MemoryEntry | None:
        """Create a memory entry from a chapter's summary."""
        if not chapter.summary:
            return None
        return await self.create_memory(chapter.id, chapter.summary)

    async def retrieve_similar(
        self, query: str, project_id: UUID, top_k: int = 5,
    ) -> list[MemoryEntry]:
        """Find similar memories by embedding cosine similarity."""
        query_embedding = await self.embed_svc.embed_query(query)
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Use raw SQL with vector distance ordering
        sql = sa_text(
            "SELECT me.id FROM memory_entries me "
            "JOIN chapters c ON me.chapter_id = c.id "
            "WHERE c.project_id = :project_id AND me.embedding IS NOT NULL "
            "ORDER BY me.embedding <=> :embedding "
            "LIMIT :limit"
        )
        result = await self.db.execute(
            sql,
            {
                "project_id": str(project_id),
                "embedding": embedding_str,
                "limit": top_k,
            },
        )
        ids = [row[0] for row in result.fetchall()]
        if not ids:
            return []
        result = await self.db.execute(
            select(MemoryEntry).where(MemoryEntry.id.in_(ids))
        )
        return list(result.scalars().all())

    async def get_chapter_memories(self, chapter_id: UUID) -> list[MemoryEntry]:
        """Get all memories for a specific chapter."""
        result = await self.db.execute(
            select(MemoryEntry).where(MemoryEntry.chapter_id == chapter_id)
        )
        return list(result.scalars().all())

