"""Memory CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.embedding_service import EmbeddingService
from app.engines.memory_engine import MemoryEngine
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry
from app.providers.registry import provider_registry
from app.schemas.memory import MemoryCreate, MemoryResponse

router = APIRouter(prefix="/api", tags=["memories"], dependencies=[Depends(verify_token)])


@router.post("/chapters/{chapter_id}/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(
    chapter_id: UUID,
    body: MemoryCreate,
    db: AsyncSession = Depends(get_db),
):
    ch = (await db.execute(select(Chapter).where(Chapter.id == chapter_id))).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")

    provider = provider_registry.get_default()
    embed_svc = EmbeddingService(db, provider)
    engine = MemoryEngine(db, embed_svc)
    mem = await engine.create_memory(chapter_id, body.summary)
    return MemoryResponse(
        id=mem.id, chapter_id=mem.chapter_id, summary=mem.summary,
        has_embedding=mem.embedding is not None,
        created_at=mem.created_at,
    )


@router.get("/chapters/{chapter_id}/memories", response_model=list[MemoryResponse])
async def list_memories(
    chapter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MemoryEntry).where(MemoryEntry.chapter_id == chapter_id)
    )
    memories = result.scalars().all()
    return [
        MemoryResponse(
            id=m.id, chapter_id=m.chapter_id, summary=m.summary,
            has_embedding=m.embedding is not None,
            created_at=m.created_at,
        )
        for m in memories
    ]
