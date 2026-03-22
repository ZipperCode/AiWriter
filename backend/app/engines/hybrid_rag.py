"""Hybrid RAG engine: vector + BM25 + graph + RRF + Jina reranker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

import httpx
from sqlalchemy import select, bindparam, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engines.embedding_service import EmbeddingService
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.relationship import Relationship
from app.models.chapter import Chapter


@dataclass
class SearchResult:
    """A single search result from any retrieval channel."""
    source: str             # "entity" | "memory" | "draft"
    source_id: UUID
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


class HybridRAGEngine:
    """Three-channel hybrid retrieval with RRF fusion and Jina reranker."""

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embed_svc = embedding_service

    async def vector_search(
        self, query_embedding: list[float], project_id: UUID, top_k: int = 20,
    ) -> list[SearchResult]:
        """Search entities and memories by vector cosine similarity."""
        results: list[SearchResult] = []
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Search entities
        entity_sql = sa_text(
            "SELECT id, name, entity_type, description, "
            "1 - (embedding <=> CAST(:emb AS vector)) as similarity "
            "FROM entities "
            "WHERE project_id = CAST(:pid AS uuid) AND embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT :k"
        ).bindparams(bindparam("emb", value=embedding_str),
                      bindparam("pid", value=str(project_id)),
                      bindparam("k", value=top_k))
        entity_rows = await self.db.execute(entity_sql)
        for row in entity_rows:
            content = f"[{row.entity_type}] {row.name}"
            if row.description:
                content += f": {row.description}"
            results.append(SearchResult(
                source="entity", source_id=row.id, content=content,
                score=float(row.similarity),
                metadata={"entity_type": row.entity_type, "name": row.name},
            ))

        # Search memory entries (join through chapters to filter by project)
        memory_sql = sa_text(
            "SELECT me.id, me.summary, "
            "1 - (me.embedding <=> CAST(:emb AS vector)) as similarity "
            "FROM memory_entries me "
            "JOIN chapters c ON me.chapter_id = c.id "
            "WHERE c.project_id = CAST(:pid AS uuid) AND me.embedding IS NOT NULL "
            "ORDER BY me.embedding <=> CAST(:emb AS vector) "
            "LIMIT :k"
        ).bindparams(bindparam("emb", value=embedding_str),
                      bindparam("pid", value=str(project_id)),
                      bindparam("k", value=top_k))
        memory_rows = await self.db.execute(memory_sql)
        for row in memory_rows:
            results.append(SearchResult(
                source="memory", source_id=row.id, content=row.summary,
                score=float(row.similarity),
                metadata={"type": "chapter_memory"},
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def bm25_search(
        self, query_text: str, project_id: UUID, top_k: int = 20,
    ) -> list[SearchResult]:
        """Search using BM25 with jieba tokenization."""
        import jieba
        from rank_bm25 import BM25Okapi

        # Build corpus from entities + memories
        docs: list[tuple[str, str, UUID]] = []  # (source, content, id)

        entities = (await self.db.execute(
            select(Entity).where(Entity.project_id == project_id)
        )).scalars().all()
        for e in entities:
            text = f"[{e.entity_type}] {e.name}"
            if e.description:
                text += f": {e.description}"
            docs.append(("entity", text, e.id))

        # Memory entries via chapter join
        memory_sql = (
            select(MemoryEntry)
            .join(Chapter, MemoryEntry.chapter_id == Chapter.id)
            .where(Chapter.project_id == project_id)
        )
        memories = (await self.db.execute(memory_sql)).scalars().all()
        for m in memories:
            docs.append(("memory", m.summary, m.id))

        if not docs:
            return []

        # Tokenize corpus and query
        tokenized_corpus = [list(jieba.cut(d[1])) for d in docs]
        tokenized_query = list(jieba.cut(query_text))

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)

        # Rank and return top_k
        indexed_scores = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True,
        )
        results = []
        for idx, score in indexed_scores[:top_k]:
            if score <= 0:
                break
            source, content, source_id = docs[idx]
            results.append(SearchResult(
                source=source, source_id=source_id, content=content,
                score=float(score), metadata={"channel": "bm25"},
            ))
        return results

    async def graph_search(
        self, entity_id: UUID, project_id: UUID, depth: int = 2,
    ) -> list[SearchResult]:
        """BFS traversal of entity relationship graph."""
        if depth <= 0:
            return []

        visited: set[UUID] = {entity_id}
        frontier: set[UUID] = {entity_id}
        results: list[SearchResult] = []

        for _ in range(depth):
            if not frontier:
                break
            next_frontier: set[UUID] = set()
            for eid in frontier:
                rels = (await self.db.execute(
                    select(Relationship).where(
                        Relationship.project_id == project_id,
                        (Relationship.source_entity_id == eid)
                        | (Relationship.target_entity_id == eid),
                    )
                )).scalars().all()

                for rel in rels:
                    neighbor_id = (
                        rel.target_entity_id
                        if rel.source_entity_id == eid
                        else rel.source_entity_id
                    )
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_frontier.add(neighbor_id)
            frontier = next_frontier

        visited.discard(entity_id)
        if visited:
            neighbors = (await self.db.execute(
                select(Entity).where(Entity.id.in_(visited))
            )).scalars().all()
            for e in neighbors:
                content = f"[{e.entity_type}] {e.name}"
                if e.description:
                    content += f": {e.description}"
                results.append(SearchResult(
                    source="entity", source_id=e.id, content=content,
                    score=1.0 / (depth + 1),
                    metadata={"name": e.name, "entity_type": e.entity_type, "channel": "graph"},
                ))
        return results

    @staticmethod
    def rrf_fusion(
        channels: list[list[SearchResult]], k: int = 60,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion across multiple result channels."""
        scores: dict[UUID, float] = {}
        best_result: dict[UUID, SearchResult] = {}

        for channel in channels:
            for rank, result in enumerate(channel, start=1):
                rrf_score = 1.0 / (k + rank)
                scores[result.source_id] = scores.get(result.source_id, 0) + rrf_score
                if result.source_id not in best_result:
                    best_result[result.source_id] = result

        fused = []
        for source_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            r = best_result[source_id]
            fused.append(SearchResult(
                source=r.source, source_id=r.source_id, content=r.content,
                score=score, metadata=r.metadata,
            ))
        return fused

    async def rerank(
        self, candidates: list[SearchResult], query: str, top_m: int = 5,
    ) -> list[SearchResult]:
        """Re-rank candidates using Jina Reranker API. Falls back to truncation."""
        if not settings.jina_api_key or not candidates:
            return candidates[:top_m]

        documents = [c.content for c in candidates]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.jina.ai/v1/rerank",
                    headers={
                        "Authorization": f"Bearer {settings.jina_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.jina_rerank_model,
                        "query": query,
                        "documents": documents,
                        "top_n": top_m,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            reranked = []
            for item in data["results"][:top_m]:
                idx = item["index"]
                r = candidates[idx]
                reranked.append(SearchResult(
                    source=r.source, source_id=r.source_id, content=r.content,
                    score=float(item["relevance_score"]),
                    metadata=r.metadata,
                ))
            return reranked
        except Exception:
            return candidates[:top_m]
