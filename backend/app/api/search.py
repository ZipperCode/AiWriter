"""RAG search API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.embedding_service import EmbeddingService
from app.engines.hybrid_rag import HybridRAGEngine
from app.providers.registry import provider_registry
from app.schemas.search import SearchRequest, SearchResultResponse, SearchResponse

router = APIRouter(prefix="/api", tags=["search"], dependencies=[Depends(verify_token)])


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    provider = provider_registry.get_default()
    embed_svc = EmbeddingService(db, provider)
    rag = HybridRAGEngine(db, embed_svc)
    results = await rag.retrieve(
        query=req.query,
        project_id=req.project_id,
        pov_entity_id=req.pov_entity_id,
        top_m=req.top_m,
    )
    return SearchResponse(
        results=[
            SearchResultResponse(
                source=r.source, source_id=r.source_id, content=r.content,
                score=r.score, metadata=r.metadata,
            )
            for r in results
        ],
        total=len(results),
    )
