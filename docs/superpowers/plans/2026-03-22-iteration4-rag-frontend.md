# Iteration 4: Hybrid RAG + Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Hybrid RAG engine (vector + BM25 + graph + RRF + Jina Reranker), memory system, WebSocket real-time push, and Next.js 15 frontend with Studio/Atlas/Dashboard pages.

**Architecture:** Three-channel retrieval (pgvector cosine, BM25 with jieba tokenization, entity-graph BFS) fused via RRF and re-ranked by Jina API. Redis Pub/Sub event bus powers WebSocket-based agent progress streaming. Next.js 15 App Router with shadcn/ui provides Studio (chapter editing + pipeline control), Atlas (ReactFlow entity graph), and Dashboard (audit/pacing visualization).

**Tech Stack:** rank-bm25, Jina Reranker v3 API, pgvector HNSW, Redis Pub/Sub, FastAPI WebSocket, Next.js 15, React 19, Tailwind CSS, shadcn/ui, ReactFlow, TanStack React Query, Zustand, Recharts

**Prerequisites:** Iteration 1-3 complete (198 tests passing, 22 DB tables, 7 agents, domain engines)

---

## File Structure

### Backend (New/Modified)

```
backend/app/
├── config.py                          # MODIFY: add RAG + Jina + WS config
├── engines/
│   ├── embedding_service.py           # NEW: embedding compute + store
│   ├── hybrid_rag.py                  # NEW: three-channel retrieval + RRF + rerank
│   ├── memory_engine.py               # NEW: chapter memory management
│   └── context_filter.py              # MODIFY: integrate RAG retrieval
├── events/
│   └── event_bus.py                   # NEW: Redis Pub/Sub event bus
├── api/
│   ├── ws.py                          # NEW: WebSocket endpoint
│   ├── search.py                      # NEW: RAG search API
│   └── memories.py                    # NEW: Memory CRUD API
├── schemas/
│   ├── search.py                      # NEW: search request/response schemas
│   └── memory.py                      # NEW: memory schemas
├── main.py                            # MODIFY: register new routers + WS
└── orchestration/
    └── executor.py                    # MODIFY: publish events to bus
```

### Backend (New Migrations)

```
backend/app/db/migrations/versions/
└── xxxx_add_hnsw_indices.py           # NEW: HNSW indices for vector columns
```

### Frontend (All New)

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── Dockerfile
├── .env.local
├── src/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout with providers
│   │   ├── page.tsx                   # Dashboard / project list
│   │   ├── projects/
│   │   │   └── [id]/
│   │   │       ├── page.tsx           # Project detail
│   │   │       ├── studio/
│   │   │       │   └── [chapterId]/
│   │   │       │       └── page.tsx   # Studio page
│   │   │       ├── atlas/
│   │   │       │   └── page.tsx       # Atlas page
│   │   │       └── dashboard/
│   │   │           └── page.tsx       # Dashboard page
│   │   └── globals.css
│   ├── lib/
│   │   ├── api.ts                     # API client
│   │   ├── ws.ts                      # WebSocket client
│   │   └── store.ts                   # Zustand store
│   ├── components/
│   │   ├── layout/
│   │   │   ├── sidebar.tsx            # Navigation sidebar
│   │   │   └── header.tsx             # Top header
│   │   ├── studio/
│   │   │   ├── chapter-tree.tsx       # Chapter tree sidebar
│   │   │   ├── content-viewer.tsx     # Content display
│   │   │   └── pipeline-panel.tsx     # Pipeline control + progress
│   │   ├── atlas/
│   │   │   ├── entity-graph.tsx       # ReactFlow graph
│   │   │   └── entity-detail.tsx      # Entity detail panel
│   │   └── dashboard/
│   │       ├── audit-radar.tsx        # Audit radar chart
│   │       ├── pacing-chart.tsx       # Pacing curves
│   │       └── stats-cards.tsx        # Summary statistics
│   └── hooks/
│       ├── use-api.ts                 # React Query hooks
│       └── use-websocket.ts           # WebSocket hook
└── components.json                    # shadcn/ui config
```

### Tests (New)

```
backend/tests/
├── test_embedding_service.py          # 6 tests
├── test_hybrid_rag.py                 # 10 tests
├── test_memory_engine.py              # 6 tests
├── test_event_bus.py                  # 5 tests
├── test_api_search.py                 # 4 tests
├── test_api_memories.py               # 4 tests
├── test_api_ws.py                     # 4 tests
├── test_context_filter_rag.py         # 4 tests
├── test_schemas_iter4.py              # 6 tests
└── test_integration_iter4.py          # 4 tests
```

---

## Task 1: RAG Dependencies + Config + HNSW Migration

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Create: `backend/app/db/migrations/versions/xxxx_add_hnsw_indices.py` (via alembic)
- Test: `backend/tests/test_config_rag.py`

- [ ] **Step 1: Write config tests**

```python
# backend/tests/test_config_rag.py
from app.config import Settings


def test_rag_config_defaults():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        auth_token="test",
    )
    assert s.embedding_dim == 1536
    assert s.rag_top_k == 20
    assert s.rag_top_m == 5
    assert s.rag_rrf_k == 60
    assert s.jina_api_key == ""
    assert s.jina_rerank_model == "jina-reranker-v2-base-multilingual"


def test_rag_config_custom():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        auth_token="test",
        rag_top_k=30,
        rag_top_m=10,
        jina_api_key="test-key",
    )
    assert s.rag_top_k == 30
    assert s.rag_top_m == 10
    assert s.jina_api_key == "test-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config_rag.py -v`
Expected: FAIL (missing attributes)

- [ ] **Step 3: Add dependencies to pyproject.toml**

Add to `[project] dependencies`:
```toml
    "rank-bm25>=0.2.2",
```

Then install:
```bash
cd backend && source .venv/bin/activate && pip install rank-bm25
```

- [ ] **Step 4: Add RAG config to Settings**

In `backend/app/config.py`, add fields to the `Settings` class:

```python
    # RAG settings
    rag_top_k: int = 20              # candidates per channel
    rag_top_m: int = 5               # final results after rerank
    rag_rrf_k: int = 60              # RRF k parameter
    jina_api_key: str = ""           # Jina Reranker API key
    jina_rerank_model: str = "jina-reranker-v2-base-multilingual"
```

- [ ] **Step 5: Run config tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config_rag.py -v`
Expected: PASS

- [ ] **Step 6: Create HNSW index migration**

```bash
cd backend && source .venv/bin/activate && alembic revision -m "add_hnsw_indices"
```

Edit the generated migration file:

```python
"""add_hnsw_indices

Revision ID: <auto>
Revises: b2498cf93c04
"""
from alembic import op

revision = "<auto>"
down_revision = "b2498cf93c04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_embedding "
        "ON entities USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_entries_embedding "
        "ON memory_entries USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_drafts_content_embedding "
        "ON drafts USING hnsw (content_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_drafts_content_embedding")
    op.execute("DROP INDEX IF EXISTS idx_memory_entries_embedding")
    op.execute("DROP INDEX IF EXISTS idx_entities_embedding")
```

- [ ] **Step 7: Run full test suite**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -v`
Expected: All 198+ tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py backend/app/db/migrations/versions/ backend/tests/test_config_rag.py
git commit -m "feat(infra): add RAG dependencies, config, and HNSW indices"
```

---

## Task 2: Embedding Service

**Files:**
- Create: `backend/app/engines/embedding_service.py`
- Test: `backend/tests/test_embedding_service.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_embedding_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.embedding_service import EmbeddingService
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter


async def _setup_project(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="V1", objective="obj", sort_order=1)
    db.add(volume)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=volume.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()
    return project, ch


async def test_compute_embedding(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    result = await svc.compute_embedding(["test text"])
    assert len(result) == 1
    assert len(result[0]) == 1536
    mock_provider.embedding.assert_called_once_with(["test text"])


async def test_compute_embedding_batch(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536, [0.2] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    result = await svc.compute_embedding(["text1", "text2"])
    assert len(result) == 2


async def test_embed_entity(db_session: AsyncSession):
    project, ch = await _setup_project(db_session)
    entity = Entity(
        project_id=project.id, name="Hero", entity_type="character",
        confidence=1.0, source="manual",
    )
    db_session.add(entity)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_entity(entity)
    assert entity.embedding is not None


async def test_embed_memory_entry(db_session: AsyncSession):
    project, ch = await _setup_project(db_session)
    mem = MemoryEntry(chapter_id=ch.id, summary="Hero found a sword")
    db_session.add(mem)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.3] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_memory_entry(mem)
    assert mem.embedding is not None


async def test_embed_text_for_query(db_session: AsyncSession):
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.7] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    vec = await svc.embed_query("search text")
    assert len(vec) == 1536


async def test_embed_entity_builds_text(db_session: AsyncSession):
    """Entity embedding text includes name, type, description, and attributes."""
    project, ch = await _setup_project(db_session)
    entity = Entity(
        project_id=project.id, name="Dragon Sword", entity_type="item",
        description="A legendary blade", attributes={"power": "fire"},
        confidence=1.0, source="manual",
    )
    db_session.add(entity)
    await db_session.flush()

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.1] * 1536]
    svc = EmbeddingService(db_session, mock_provider)
    await svc.embed_entity(entity)
    call_args = mock_provider.embedding.call_args[0][0]
    text = call_args[0]
    assert "Dragon Sword" in text
    assert "item" in text
    assert "fire" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_embedding_service.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement EmbeddingService**

```python
# backend/app/engines/embedding_service.py
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
        # Use first 2000 chars for embedding to stay within limits
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
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_embedding_service.py -v`
Expected: All 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/embedding_service.py backend/tests/test_embedding_service.py
git commit -m "feat(engines): add embedding service for compute and store"
```

---

## Task 3: HybridRAGEngine - Vector Search

**Files:**
- Create: `backend/app/engines/hybrid_rag.py`
- Test: `backend/tests/test_hybrid_rag.py`

- [ ] **Step 1: Write tests for vector search**

```python
# backend/tests/test_hybrid_rag.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
from app.engines.embedding_service import EmbeddingService
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.relationship import Relationship


async def _setup_rag_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()

    # Entities with embeddings
    e1 = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        description="主角，天才少年", confidence=1.0, source="manual",
        embedding=[0.9] + [0.0] * 1535,
    )
    e2 = Entity(
        project_id=project.id, name="青云宗", entity_type="faction",
        description="修仙门派", confidence=1.0, source="manual",
        embedding=[0.0] + [0.9] + [0.0] * 1534,
    )
    e3 = Entity(
        project_id=project.id, name="Dragon Sword", entity_type="item",
        description="A legendary blade", confidence=1.0, source="manual",
        embedding=[0.0] * 2 + [0.9] + [0.0] * 1533,
    )
    db.add_all([e1, e2, e3])
    await db.flush()

    # Memory entries
    m1 = MemoryEntry(
        chapter_id=ch.id, summary="叶辰来到青云宗参加入门测试",
        embedding=[0.85] + [0.1] + [0.0] * 1534,
    )
    m2 = MemoryEntry(
        chapter_id=ch.id, summary="叶辰获得神秘传承",
        embedding=[0.8] + [0.0] * 1535,
    )
    db.add_all([m1, m2])
    await db.flush()

    # Relationships
    rel = Relationship(
        project_id=project.id, source_entity_id=e1.id, target_entity_id=e2.id,
        relation_type="belongs_to", description="叶辰是青云宗弟子",
    )
    db.add(rel)
    await db.flush()

    return project, ch, e1, e2, e3, m1, m2, rel


def test_search_result_creation():
    sr = SearchResult(
        source="entity", source_id=uuid4(), content="test",
        score=0.9, metadata={"type": "character"},
    )
    assert sr.source == "entity"
    assert sr.score == 0.9


async def test_vector_search_entities(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    # Query embedding close to e1 (叶辰)
    query_embedding = [0.88] + [0.05] + [0.0] * 1534
    results = await rag.vector_search(query_embedding, project.id, top_k=3)
    assert len(results) > 0
    assert results[0].source in ("entity", "memory")
    # Results should be sorted by score descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


async def test_vector_search_empty_project(db_session: AsyncSession):
    project = Project(title="Empty", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.vector_search([0.1] * 1536, project.id, top_k=5)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py::test_search_result_creation tests/test_hybrid_rag.py::test_vector_search_entities tests/test_hybrid_rag.py::test_vector_search_empty_project -v`
Expected: FAIL

- [ ] **Step 3: Implement SearchResult and vector search**

```python
# backend/app/engines/hybrid_rag.py
"""Hybrid RAG engine: vector + BM25 + graph + RRF + Jina reranker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

import httpx
from sqlalchemy import select, text as sa_text
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
            "1 - (embedding <=> :emb::vector) as similarity "
            "FROM entities "
            "WHERE project_id = :pid AND embedding IS NOT NULL "
            "ORDER BY embedding <=> :emb::vector "
            "LIMIT :k"
        )
        entity_rows = await self.db.execute(
            entity_sql,
            {"emb": embedding_str, "pid": str(project_id), "k": top_k},
        )
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
            "1 - (me.embedding <=> :emb::vector) as similarity "
            "FROM memory_entries me "
            "JOIN chapters c ON me.chapter_id = c.id "
            "WHERE c.project_id = :pid AND me.embedding IS NOT NULL "
            "ORDER BY me.embedding <=> :emb::vector "
            "LIMIT :k"
        )
        memory_rows = await self.db.execute(
            memory_sql,
            {"emb": embedding_str, "pid": str(project_id), "k": top_k},
        )
        for row in memory_rows:
            results.append(SearchResult(
                source="memory", source_id=row.id, content=row.summary,
                score=float(row.similarity),
                metadata={"type": "chapter_memory"},
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/hybrid_rag.py backend/tests/test_hybrid_rag.py
git commit -m "feat(engines): add hybrid RAG engine with vector search"
```

---

## Task 4: HybridRAGEngine - BM25 Search

**Files:**
- Modify: `backend/app/engines/hybrid_rag.py`
- Modify: `backend/tests/test_hybrid_rag.py`

- [ ] **Step 1: Add BM25 tests**

Append to `backend/tests/test_hybrid_rag.py`:

```python
async def test_bm25_search(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    results = await rag.bm25_search("叶辰 青云宗", project.id, top_k=5)
    assert len(results) > 0
    # Should find entities/memories mentioning 叶辰 or 青云宗
    contents = " ".join(r.content for r in results)
    assert "叶辰" in contents or "青云宗" in contents


async def test_bm25_search_no_results(db_session: AsyncSession):
    project = Project(title="Empty", genre="xuanhuan", status="active", settings={})
    db_session.add(project)
    await db_session.flush()
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.bm25_search("不存在的内容", project.id, top_k=5)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py::test_bm25_search tests/test_hybrid_rag.py::test_bm25_search_no_results -v`
Expected: FAIL

- [ ] **Step 3: Implement BM25 search**

Add to `HybridRAGEngine` in `backend/app/engines/hybrid_rag.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py -v`
Expected: All 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/hybrid_rag.py backend/tests/test_hybrid_rag.py
git commit -m "feat(engines): add BM25 search to hybrid RAG"
```

---

## Task 5: HybridRAGEngine - Graph Search + RRF Fusion + Rerank

**Files:**
- Modify: `backend/app/engines/hybrid_rag.py`
- Modify: `backend/tests/test_hybrid_rag.py`

- [ ] **Step 1: Add tests for graph search, RRF, and rerank**

Append to `backend/tests/test_hybrid_rag.py`:

```python
async def test_graph_search(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    results = await rag.graph_search(e1.id, project.id, depth=1)
    assert len(results) > 0
    # Should find 青云宗 (related to 叶辰)
    names = [r.metadata.get("name") for r in results]
    assert "青云宗" in names


async def test_graph_search_depth_zero(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.graph_search(e1.id, project.id, depth=0)
    assert len(results) == 0  # depth 0 = no traversal


def test_rrf_fusion():
    """Test RRF fusion combines and re-scores results."""
    id1, id2, id3 = uuid4(), uuid4(), uuid4()
    channel_a = [
        SearchResult("entity", id1, "A", 0.9),
        SearchResult("entity", id2, "B", 0.8),
    ]
    channel_b = [
        SearchResult("entity", id2, "B", 5.0),
        SearchResult("entity", id3, "C", 3.0),
    ]
    fused = HybridRAGEngine.rrf_fusion([channel_a, channel_b], k=60)
    assert len(fused) == 3
    # id2 appears in both channels, should have highest RRF score
    id2_result = next(r for r in fused if r.source_id == id2)
    id1_result = next(r for r in fused if r.source_id == id1)
    assert id2_result.score > id1_result.score


async def test_rerank_with_mock(db_session: AsyncSession):
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    candidates = [
        SearchResult("entity", uuid4(), "叶辰是天才", 0.5),
        SearchResult("memory", uuid4(), "青云宗入门测试", 0.4),
        SearchResult("entity", uuid4(), "Dragon Sword", 0.3),
    ]

    # Mock Jina API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.85},
            {"index": 2, "relevance_score": 0.60},
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        results = await rag.rerank(candidates, "青云宗测试", top_m=2)
        assert len(results) == 2
        assert results[0].score == 0.95


async def test_rerank_fallback_no_api_key(db_session: AsyncSession):
    """When no Jina API key, rerank returns candidates as-is (truncated)."""
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    candidates = [
        SearchResult("entity", uuid4(), "A", 0.9),
        SearchResult("entity", uuid4(), "B", 0.8),
    ]
    with patch.object(settings, "jina_api_key", ""):
        results = await rag.rerank(candidates, "query", top_m=1)
        assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py::test_graph_search tests/test_hybrid_rag.py::test_rrf_fusion tests/test_hybrid_rag.py::test_rerank_with_mock -v`
Expected: FAIL

- [ ] **Step 3: Implement graph search, RRF, and rerank**

Add to `HybridRAGEngine` in `backend/app/engines/hybrid_rag.py`:

```python
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
                # Find relationships in both directions
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

        # Fetch entity details for discovered nodes
        visited.discard(entity_id)  # exclude the starting entity
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
                    score=1.0 / (depth + 1),  # closer = higher score
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
            # Fallback: return candidates by existing score
            return candidates[:top_m]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py -v`
Expected: All 10 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/hybrid_rag.py backend/tests/test_hybrid_rag.py
git commit -m "feat(engines): add graph search, RRF fusion, and Jina reranker"
```

---

## Task 6: HybridRAGEngine - Full Retrieve Pipeline

**Files:**
- Modify: `backend/app/engines/hybrid_rag.py`
- Modify: `backend/tests/test_hybrid_rag.py`

- [ ] **Step 1: Add retrieve pipeline test**

Append to `backend/tests/test_hybrid_rag.py`:

```python
async def test_retrieve_full_pipeline(db_session: AsyncSession):
    project, ch, e1, e2, e3, m1, m2, rel = await _setup_rag_data(db_session)

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.88] + [0.05] + [0.0] * 1534]
    embed_svc = EmbeddingService(db_session, mock_provider)
    rag = HybridRAGEngine(db_session, embed_svc)

    # No Jina key → rerank fallback
    with patch.object(settings, "jina_api_key", ""):
        results = await rag.retrieve(
            query="叶辰的修炼",
            project_id=project.id,
            pov_entity_id=e1.id,
            top_m=3,
        )
    assert len(results) > 0
    assert len(results) <= 3
    # All results should have content
    for r in results:
        assert r.content
        assert r.score > 0
```

- [ ] **Step 2: Implement retrieve method**

Add to `HybridRAGEngine`:

```python
    async def retrieve(
        self,
        query: str,
        project_id: UUID,
        pov_entity_id: UUID | None = None,
        top_m: int | None = None,
    ) -> list[SearchResult]:
        """Full retrieval pipeline: vector + BM25 + graph → RRF → rerank."""
        top_k = settings.rag_top_k
        if top_m is None:
            top_m = settings.rag_top_m

        # Compute query embedding
        query_embedding = await self.embed_svc.embed_query(query)

        # Three channels in parallel (conceptually; sequential for simplicity)
        vector_results = await self.vector_search(query_embedding, project_id, top_k)
        bm25_results = await self.bm25_search(query, project_id, top_k)

        channels = [vector_results, bm25_results]

        # Graph search only if POV entity provided
        if pov_entity_id:
            graph_results = await self.graph_search(pov_entity_id, project_id, depth=2)
            channels.append(graph_results)

        # RRF fusion
        fused = self.rrf_fusion(channels, k=settings.rag_rrf_k)

        # Rerank top candidates
        candidates = fused[: top_k * 2]  # over-fetch for reranker
        return await self.rerank(candidates, query, top_m)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_hybrid_rag.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/hybrid_rag.py backend/tests/test_hybrid_rag.py
git commit -m "feat(engines): add full retrieve pipeline to hybrid RAG"
```

---

## Task 7: Memory Engine

**Files:**
- Create: `backend/app/engines/memory_engine.py`
- Test: `backend/tests/test_memory_engine.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_memory_engine.py
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.engines.memory_engine import MemoryEngine
from app.engines.embedding_service import EmbeddingService
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry


async def _setup_memory_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch1 = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="final", summary="叶辰来到青云宗",
    )
    ch2 = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch2",
        sort_order=2, status="final", summary="叶辰参加入门测试",
    )
    db.add_all([ch1, ch2])
    await db.flush()
    return project, ch1, ch2


async def test_create_memory(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem = await engine.create_memory(ch1.id, "叶辰来到青云宗参加修炼")
    assert mem.id is not None
    assert mem.summary == "叶辰来到青云宗参加修炼"
    assert mem.embedding is not None


async def test_retrieve_similar(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    # Create two memories
    await engine.create_memory(ch1.id, "叶辰来到青云宗")
    mock_provider.embedding.return_value = [[0.6] * 1536]
    await engine.create_memory(ch2.id, "叶辰参加入门测试")

    # Query
    mock_provider.embedding.return_value = [[0.55] * 1536]
    results = await engine.retrieve_similar("叶辰的经历", project.id, top_k=5)
    assert len(results) == 2


async def test_get_chapter_memories(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    await engine.create_memory(ch1.id, "Memory 1")
    await engine.create_memory(ch1.id, "Memory 2")
    mems = await engine.get_chapter_memories(ch1.id)
    assert len(mems) == 2


async def test_create_memories_from_chapter(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    # Create memory from chapter summary
    mem = await engine.create_memory_from_chapter(ch1)
    assert mem is not None
    assert "叶辰来到青云宗" in mem.summary


async def test_create_memory_from_chapter_no_summary(db_session: AsyncSession):
    project, ch1, ch2 = await _setup_memory_data(db_session)
    ch1.summary = None
    mock_provider = AsyncMock()
    embed_svc = EmbeddingService(db_session, mock_provider)
    engine = MemoryEngine(db_session, embed_svc)

    mem = await engine.create_memory_from_chapter(ch1)
    assert mem is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_memory_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement MemoryEngine**

```python
# backend/app/engines/memory_engine.py
"""Memory engine: chapter memory creation and similarity retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text as sa_text
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

        sql = sa_text(
            "SELECT me.id "
            "FROM memory_entries me "
            "JOIN chapters c ON me.chapter_id = c.id "
            "WHERE c.project_id = :pid AND me.embedding IS NOT NULL "
            "ORDER BY me.embedding <=> :emb::vector "
            "LIMIT :k"
        )
        rows = await self.db.execute(
            sql, {"emb": embedding_str, "pid": str(project_id), "k": top_k},
        )
        ids = [row.id for row in rows]
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
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_memory_engine.py -v`
Expected: All 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/memory_engine.py backend/tests/test_memory_engine.py
git commit -m "feat(engines): add memory engine with embedding retrieval"
```

---

## Task 8: RAG Schemas + Search/Memory APIs

**Files:**
- Create: `backend/app/schemas/search.py`
- Create: `backend/app/schemas/memory.py`
- Create: `backend/app/api/search.py`
- Create: `backend/app/api/memories.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_schemas_iter4.py`
- Test: `backend/tests/test_api_search.py`
- Test: `backend/tests/test_api_memories.py`

- [ ] **Step 1: Write schema tests**

```python
# backend/tests/test_schemas_iter4.py
import pytest
from uuid import uuid4
from app.schemas.search import SearchRequest, SearchResultResponse, SearchResponse
from app.schemas.memory import MemoryCreate, MemoryResponse


def test_search_request_defaults():
    req = SearchRequest(query="test query", project_id=uuid4())
    assert req.top_m == 5
    assert req.pov_entity_id is None


def test_search_request_with_pov():
    pid = uuid4()
    eid = uuid4()
    req = SearchRequest(query="test", project_id=pid, pov_entity_id=eid, top_m=10)
    assert req.pov_entity_id == eid
    assert req.top_m == 10


def test_search_result_response():
    r = SearchResultResponse(
        source="entity", source_id=uuid4(), content="test", score=0.9, metadata={},
    )
    assert r.source == "entity"
    assert r.score == 0.9


def test_search_response():
    r = SearchResponse(results=[], total=0)
    assert r.total == 0


def test_memory_create():
    m = MemoryCreate(summary="Test memory")
    assert m.summary == "Test memory"


def test_memory_response():
    m = MemoryResponse(
        id=uuid4(), chapter_id=uuid4(), summary="Test",
        has_embedding=True, created_at="2026-01-01T00:00:00",
    )
    assert m.has_embedding is True
```

- [ ] **Step 2: Implement schemas**

```python
# backend/app/schemas/search.py
"""Search-related request/response schemas."""

from uuid import UUID
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    project_id: UUID
    pov_entity_id: UUID | None = None
    top_m: int = Field(default=5, ge=1, le=50)


class SearchResultResponse(BaseModel):
    source: str
    source_id: UUID
    content: str
    score: float
    metadata: dict = {}


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total: int
```

```python
# backend/app/schemas/memory.py
"""Memory-related request/response schemas."""

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    summary: str = Field(..., min_length=1, max_length=2000)


class MemoryResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    summary: str
    has_embedding: bool
    created_at: str | datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Write API tests**

```python
# backend/tests/test_api_search.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.api.deps import get_db, verify_token
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity


async def _setup_search_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()
    e = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        description="主角", confidence=1.0, source="manual",
        embedding=[0.5] * 1536,
    )
    db.add(e)
    await db.flush()
    return project, ch, e


async def test_search_endpoint(db_session: AsyncSession):
    project, ch, e = await _setup_search_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    with patch("app.api.search.get_embedding_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_svc.embed_query.return_value = [0.5] * 1536
        mock_get_svc.return_value = mock_svc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/search",
                json={"query": "叶辰", "project_id": str(project.id)},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data

    app.dependency_overrides.clear()


async def test_search_endpoint_empty_query(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/search",
            json={"query": "", "project_id": str(uuid4())},
        )
    assert resp.status_code == 422

    app.dependency_overrides.clear()


async def test_search_endpoint_with_pov(db_session: AsyncSession):
    project, ch, e = await _setup_search_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    with patch("app.api.search.get_embedding_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_svc.embed_query.return_value = [0.5] * 1536
        mock_get_svc.return_value = mock_svc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/search",
                json={
                    "query": "叶辰", "project_id": str(project.id),
                    "pov_entity_id": str(e.id),
                },
            )
        assert resp.status_code == 200

    app.dependency_overrides.clear()


async def test_search_unknown_project(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    with patch("app.api.search.get_embedding_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_svc.embed_query.return_value = [0.5] * 1536
        mock_get_svc.return_value = mock_svc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/search",
                json={"query": "test", "project_id": str(uuid4())},
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    app.dependency_overrides.clear()
```

```python
# backend/tests/test_api_memories.py
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.api.deps import get_db, verify_token
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.memory_entry import MemoryEntry


async def _setup_mem_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()
    ch = Chapter(
        project_id=project.id, volume_id=vol.id, title="Ch1",
        sort_order=1, status="draft",
    )
    db.add(ch)
    await db.flush()
    return project, ch


async def test_create_memory(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    with patch("app.api.memories.get_embedding_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_svc.embed_query.return_value = [0.5] * 1536
        from app.engines.embedding_service import EmbeddingService
        mock_engine = AsyncMock(spec=EmbeddingService)
        mock_engine.embed_memory_entry = AsyncMock()
        mock_get_svc.return_value = mock_svc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/chapters/{ch.id}/memories",
                json={"summary": "叶辰来到青云宗"},
            )
        assert resp.status_code == 201

    app.dependency_overrides.clear()


async def test_list_memories(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    mem = MemoryEntry(chapter_id=ch.id, summary="Test memory")
    db_session.add(mem)
    await db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/chapters/{ch.id}/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    app.dependency_overrides.clear()


async def test_list_memories_empty(db_session: AsyncSession):
    project, ch = await _setup_mem_data(db_session)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/chapters/{ch.id}/memories")
    assert resp.status_code == 200
    assert resp.json() == []

    app.dependency_overrides.clear()


async def test_create_memory_chapter_not_found(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    with patch("app.api.memories.get_embedding_service") as mock_get_svc:
        mock_svc = AsyncMock()
        mock_get_svc.return_value = mock_svc

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/chapters/{uuid4()}/memories",
                json={"summary": "test"},
            )
        assert resp.status_code == 404

    app.dependency_overrides.clear()
```

- [ ] **Step 4: Implement API endpoints**

```python
# backend/app/api/search.py
"""RAG search API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.embedding_service import EmbeddingService
from app.engines.hybrid_rag import HybridRAGEngine
from app.providers.registry import provider_registry
from app.schemas.search import SearchRequest, SearchResultResponse, SearchResponse

router = APIRouter(prefix="/api", tags=["search"], dependencies=[Depends(verify_token)])


def get_embedding_service(db: AsyncSession = Depends(get_db)) -> EmbeddingService:
    provider = provider_registry.get_default()
    return EmbeddingService(db, provider)


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
    embed_svc: EmbeddingService = Depends(get_embedding_service),
):
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
```

```python
# backend/app/api/memories.py
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


def get_embedding_service(db: AsyncSession = Depends(get_db)) -> EmbeddingService:
    provider = provider_registry.get_default()
    return EmbeddingService(db, provider)


@router.post("/chapters/{chapter_id}/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(
    chapter_id: UUID,
    body: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    embed_svc: EmbeddingService = Depends(get_embedding_service),
):
    # Verify chapter exists
    ch = (await db.execute(select(Chapter).where(Chapter.id == chapter_id))).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")

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
```

- [ ] **Step 5: Register routers in main.py**

Add to `backend/app/main.py`:

```python
from app.api.search import router as search_router
from app.api.memories import router as memories_router

app.include_router(search_router)
app.include_router(memories_router)
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_schemas_iter4.py tests/test_api_search.py tests/test_api_memories.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/search.py backend/app/schemas/memory.py backend/app/api/search.py backend/app/api/memories.py backend/app/main.py backend/tests/test_schemas_iter4.py backend/tests/test_api_search.py backend/tests/test_api_memories.py
git commit -m "feat(api): add RAG search and memory CRUD endpoints"
```

---

## Task 9: ContextFilter RAG Integration

**Files:**
- Modify: `backend/app/engines/context_filter.py`
- Test: `backend/tests/test_context_filter_rag.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_context_filter_rag.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.context_filter import ContextFilter
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.truth_file import TruthFile
from app.models.scene_card import SceneCard


async def _setup_rag_context_data(db: AsyncSession):
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    volume = Volume(project_id=project.id, title="V1", objective="Test", sort_order=1)
    db.add(volume)
    await db.flush()
    pov = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        knowledge_boundary={"known_events": ["arrived"]},
        confidence=1.0, source="manual",
    )
    db.add(pov)
    await db.flush()
    # Create 6 chapters to trigger RAG mode (chapter 6+)
    chapters = []
    for i in range(1, 7):
        ch = Chapter(
            project_id=project.id, volume_id=volume.id,
            title=f"Chapter {i}", sort_order=i,
            pov_character_id=pov.id,
            status="final" if i < 6 else "planned",
            summary=f"第{i}章内容摘要",
        )
        db.add(ch)
        await db.flush()
        chapters.append(ch)
    tf_bible = TruthFile(
        project_id=project.id, file_type="story_bible",
        content={"world": "修仙世界"}, version=1,
    )
    tf_state = TruthFile(
        project_id=project.id, file_type="current_state",
        content={"chapter": 5}, version=1,
    )
    db.add_all([tf_bible, tf_state])
    await db.flush()
    sc = SceneCard(
        chapter_id=chapters[-1].id, sort_order=1,
        pov_character_id=pov.id, location="大殿",
        goal="测试", conflict="强敌",
    )
    db.add(sc)
    await db.flush()
    return project, volume, pov, chapters


async def test_context_with_rag_section(db_session: AsyncSession):
    """After chapter 5, context should include RAG results section."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[-1]  # Chapter 6

    # Mock RAG results
    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        from app.engines.hybrid_rag import SearchResult
        mock_rag.retrieve.return_value = [
            SearchResult("entity", uuid4(), "RAG result content", 0.9),
        ]
        with patch("app.engines.context_filter.EmbeddingService"):
            cf = ContextFilter(db_session)
            ctx = await cf.assemble_context(target_ch.id, pov.id)

    assert "rag_results" in ctx["sections"]
    assert "RAG result content" in ctx["sections"]["rag_results"]


async def test_context_without_rag_early_chapters(db_session: AsyncSession):
    """Chapters 1-5 should not use RAG (full context mode)."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[0]  # Chapter 1

    cf = ContextFilter(db_session)
    ctx = await cf.assemble_context(target_ch.id, pov.id)
    # Early chapters don't have RAG section
    assert "rag_results" not in ctx.get("sections", {})


async def test_progressive_context_strategy(db_session: AsyncSession):
    """Verify progressive context: ch1-5 = full, ch6+ = RAG."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)

    cf = ContextFilter(db_session)
    strategy = cf._get_context_strategy(chapters[0].sort_order)
    assert strategy == "full"

    strategy = cf._get_context_strategy(chapters[-1].sort_order)
    assert strategy == "progressive"


async def test_context_rag_fallback_on_error(db_session: AsyncSession):
    """If RAG fails, context should still work without RAG section."""
    project, volume, pov, chapters = await _setup_rag_context_data(db_session)
    target_ch = chapters[-1]

    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        mock_rag.retrieve.side_effect = Exception("RAG failed")
        with patch("app.engines.context_filter.EmbeddingService"):
            cf = ContextFilter(db_session)
            ctx = await cf.assemble_context(target_ch.id, pov.id)

    # Should still have valid context without RAG
    assert ctx["context_tokens"] > 0
    assert "rag_results" not in ctx["sections"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_context_filter_rag.py -v`
Expected: FAIL

- [ ] **Step 3: Modify ContextFilter to integrate RAG**

In `backend/app/engines/context_filter.py`, add:

1. Import HybridRAGEngine and EmbeddingService
2. Add `_get_context_strategy(sort_order)` method
3. Add `_get_rag_section(project_id, pov_character_id, chapter)` method
4. Modify `assemble_context` to use progressive strategy

Key changes:
- For chapters 1-5: inject full prior chapter summaries (existing behavior)
- For chapters 6-20: setting summary + last 3 chapters full + earlier summaries
- For chapters 21+: setting summary + last 2 chapters + RAG + truth file snapshot

```python
# Add to ContextFilter.__init__:
from app.engines.hybrid_rag import HybridRAGEngine
from app.engines.embedding_service import EmbeddingService
from app.providers.registry import provider_registry

# Add _get_context_strategy method:
@staticmethod
def _get_context_strategy(sort_order: int) -> str:
    if sort_order <= 5:
        return "full"
    return "progressive"

# Add _get_rag_section method:
async def _get_rag_section(self, project_id, pov_character_id, chapter) -> str | None:
    try:
        provider = provider_registry.get_default()
        embed_svc = EmbeddingService(self.db, provider)
        rag = HybridRAGEngine(self.db, embed_svc)
        query = f"{chapter.title} {chapter.summary or ''}"
        results = await rag.retrieve(
            query=query, project_id=project_id,
            pov_entity_id=pov_character_id, top_m=5,
        )
        if not results:
            return None
        lines = ["## RAG检索结果"]
        for r in results:
            lines.append(f"- [{r.source}] {r.content}")
        return "\n".join(lines)
    except Exception:
        return None

# In assemble_context, after building sections, add:
strategy = self._get_context_strategy(chapter.sort_order)
if strategy == "progressive":
    rag_text = await self._get_rag_section(chapter.project_id, pov_character_id, chapter)
    if rag_text:
        sections["rag_results"] = rag_text
```

- [ ] **Step 4: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_context_filter_rag.py tests/test_context_filter.py tests/test_context_filter_v2.py -v`
Expected: All PASS (new + old tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/context_filter.py backend/tests/test_context_filter_rag.py
git commit -m "feat(engines): integrate RAG into context filter with progressive strategy"
```

---

## Task 10: Event Bus + WebSocket Infrastructure

**Files:**
- Create: `backend/app/events/__init__.py`
- Create: `backend/app/events/event_bus.py`
- Create: `backend/app/api/ws.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/orchestration/executor.py`
- Test: `backend/tests/test_event_bus.py`
- Test: `backend/tests/test_api_ws.py`

- [ ] **Step 1: Write event bus tests**

```python
# backend/tests/test_event_bus.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from app.events.event_bus import EventBus, PipelineEvent


def test_pipeline_event_creation():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
        data={"phase": 1},
    )
    assert event.event_type == "agent_start"
    assert event.agent_name == "writer"


def test_pipeline_event_to_json():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_complete",
        agent_name="auditor",
        data={"score": 85},
    )
    j = event.to_json()
    assert '"agent_complete"' in j
    assert '"auditor"' in j


async def test_event_bus_publish():
    mock_redis = AsyncMock()
    bus = EventBus(mock_redis)
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
    )
    await bus.publish(event)
    mock_redis.publish.assert_called_once()
    channel = mock_redis.publish.call_args[0][0]
    assert "pipeline:" in channel


async def test_event_bus_subscribe():
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub

    # Simulate receiving one message then stopping
    job_id = uuid4()
    event = PipelineEvent(
        job_run_id=job_id,
        event_type="agent_complete",
        agent_name="writer",
    )
    mock_pubsub.get_message = AsyncMock(
        side_effect=[
            {"type": "message", "data": event.to_json().encode()},
            None,  # No more messages
        ]
    )

    bus = EventBus(mock_redis)
    events = []
    async for e in bus.subscribe(job_id):
        events.append(e)
        break  # Exit after first event

    assert len(events) == 1
    assert events[0].event_type == "agent_complete"
    mock_pubsub.subscribe.assert_called_once()


async def test_event_bus_channel_name():
    job_id = uuid4()
    assert EventBus.channel_name(job_id) == f"pipeline:{job_id}"
```

- [ ] **Step 2: Implement EventBus**

```python
# backend/app/events/__init__.py
```

```python
# backend/app/events/event_bus.py
"""Redis Pub/Sub event bus for pipeline progress."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import UUID

from redis.asyncio import Redis


@dataclass
class PipelineEvent:
    """Event published during pipeline execution."""
    job_run_id: UUID
    event_type: str         # agent_start | agent_progress | agent_complete | agent_error
    agent_name: str = ""
    data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps({
            "job_run_id": str(self.job_run_id),
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> PipelineEvent:
        d = json.loads(raw)
        return cls(
            job_run_id=UUID(d["job_run_id"]),
            event_type=d["event_type"],
            agent_name=d.get("agent_name", ""),
            data=d.get("data", {}),
            timestamp=d.get("timestamp", ""),
        )

    @staticmethod
    def channel_name(job_run_id: UUID) -> str:
        return f"pipeline:{job_run_id}"


class EventBus:
    """Redis Pub/Sub event bus."""

    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def channel_name(job_run_id: UUID) -> str:
        return PipelineEvent.channel_name(job_run_id)

    async def publish(self, event: PipelineEvent) -> None:
        channel = self.channel_name(event.job_run_id)
        await self.redis.publish(channel, event.to_json())

    async def subscribe(self, job_run_id: UUID) -> AsyncIterator[PipelineEvent]:
        channel = self.channel_name(job_run_id)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    raw = msg["data"]
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    yield PipelineEvent.from_json(raw)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
```

- [ ] **Step 3: Write WebSocket API tests**

```python
# backend/tests/test_api_ws.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app.events.event_bus import PipelineEvent


def test_ws_route_registered():
    """WebSocket route should be registered."""
    routes = [r.path for r in app.routes]
    assert "/ws/{job_run_id}" in routes or any("/ws/" in r for r in routes)


async def test_ws_endpoint_health(db_session):
    """HTTP GET to WS endpoint should return 400 (not a WS upgrade)."""
    from app.api.deps import get_db, verify_token
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[verify_token] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/ws/{uuid4()}")
    # WebSocket endpoint rejects non-WS requests
    assert resp.status_code in (400, 403, 426)

    app.dependency_overrides.clear()


async def test_pipeline_event_serialization():
    event = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_start",
        agent_name="writer",
        data={"phase": 1},
    )
    j = event.to_json()
    restored = PipelineEvent.from_json(j)
    assert restored.event_type == event.event_type
    assert restored.agent_name == event.agent_name
    assert restored.data == event.data


async def test_pipeline_event_from_json_roundtrip():
    original = PipelineEvent(
        job_run_id=uuid4(),
        event_type="agent_error",
        agent_name="auditor",
        data={"error": "timeout"},
    )
    restored = PipelineEvent.from_json(original.to_json())
    assert str(restored.job_run_id) == str(original.job_run_id)
```

- [ ] **Step 4: Implement WebSocket endpoint**

```python
# backend/app/api/ws.py
"""WebSocket endpoint for real-time pipeline progress."""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.config import settings
from app.events.event_bus import EventBus

router = APIRouter()


@router.websocket("/ws/{job_run_id}")
async def pipeline_ws(websocket: WebSocket, job_run_id: UUID):
    """Stream pipeline events via WebSocket."""
    await websocket.accept()

    redis = Redis.from_url(settings.redis_url)
    bus = EventBus(redis)

    try:
        async for event in bus.subscribe(job_run_id):
            await websocket.send_text(event.to_json())
            if event.event_type in ("pipeline_complete", "pipeline_error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await redis.close()
```

- [ ] **Step 5: Register WebSocket router and update main.py**

Add to `backend/app/main.py`:

```python
from app.api.ws import router as ws_router

app.include_router(ws_router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_event_bus.py tests/test_api_ws.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/events/ backend/app/api/ws.py backend/app/main.py backend/tests/test_event_bus.py backend/tests/test_api_ws.py
git commit -m "feat(infra): add Redis event bus and WebSocket endpoint"
```

---

## Task 11: Next.js 15 Project Scaffold

**Files:**
- Create: `frontend/` (entire project scaffold)

- [ ] **Step 1: Create Next.js project**

```bash
cd /home/zipper/Projects/AiWriter
rm frontend/.gitkeep
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

- [ ] **Step 2: Add dependencies**

```bash
cd frontend
npm install @tanstack/react-query zustand @xyflow/react recharts lucide-react axios
npm install -D @types/node
```

- [ ] **Step 3: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init -d
npx shadcn@latest add button card input textarea badge separator scroll-area tabs sheet dialog alert dropdown-menu tooltip
```

- [ ] **Step 4: Create environment config**

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_AUTH_TOKEN=dev-token-change-me
```

- [ ] **Step 5: Create Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 6: Update next.config.ts for standalone output**

```typescript
// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 7: Update docker-compose.yml**

Add frontend service to `docker-compose.yml`:

```yaml
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on:
      backend: { condition: service_started }
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
      NEXT_PUBLIC_WS_URL: ws://backend:8000
```

- [ ] **Step 8: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 9: Commit**

```bash
cd /home/zipper/Projects/AiWriter
git add frontend/ docker-compose.yml
git commit -m "feat(frontend): scaffold Next.js 15 with Tailwind + shadcn/ui"
```

---

## Task 12: API Client + Auth + Layout

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/store.ts`
- Create: `frontend/src/components/layout/sidebar.tsx`
- Create: `frontend/src/components/layout/header.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/providers.tsx`
- Modify: `frontend/src/app/page.tsx` (project list)

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/lib/api.ts
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_TOKEN = process.env.NEXT_PUBLIC_AUTH_TOKEN || "";

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    Authorization: `Bearer ${AUTH_TOKEN}`,
    "Content-Type": "application/json",
  },
});

// Types
export interface Project {
  id: string;
  title: string;
  genre: string;
  status: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Volume {
  id: string;
  project_id: string;
  title: string;
  objective: string;
  sort_order: number;
}

export interface Chapter {
  id: string;
  project_id: string;
  volume_id: string;
  title: string;
  sort_order: number;
  status: string;
  summary: string | null;
  pov_character_id: string | null;
}

export interface Entity {
  id: string;
  project_id: string;
  name: string;
  entity_type: string;
  description: string | null;
  attributes: Record<string, unknown>;
}

export interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  description: string | null;
}

export interface AuditDimension {
  id: number;
  name: string;
  zh_name: string;
  category: string;
  is_deterministic: boolean;
}

export interface PacingAnalysis {
  chapters: Array<{
    chapter_id: string;
    strand: string;
    emotion_level: number;
  }>;
  strand_ratios: Record<string, number>;
}

// API functions
export const projectsApi = {
  list: () => api.get<Project[]>("/api/projects").then((r) => r.data),
  get: (id: string) => api.get<Project>(`/api/projects/${id}`).then((r) => r.data),
  create: (data: Partial<Project>) => api.post<Project>("/api/projects", data).then((r) => r.data),
};

export const volumesApi = {
  list: (projectId: string) =>
    api.get<Volume[]>(`/api/projects/${projectId}/volumes`).then((r) => r.data),
};

export const chaptersApi = {
  list: (projectId: string) =>
    api.get<Chapter[]>(`/api/projects/${projectId}/chapters`).then((r) => r.data),
  get: (id: string) => api.get<Chapter>(`/api/chapters/${id}`).then((r) => r.data),
};

export const entitiesApi = {
  list: (projectId: string) =>
    api.get<Entity[]>(`/api/projects/${projectId}/entities`).then((r) => r.data),
  relationships: (projectId: string) =>
    api.get<Relationship[]>(`/api/projects/${projectId}/entities/relationships`).then((r) => r.data),
};

export const pipelineApi = {
  run: (chapterId: string) =>
    api.post("/api/pipeline/run", { chapter_id: chapterId }).then((r) => r.data),
};

export const auditApi = {
  dimensions: () =>
    api.get<{ dimensions: AuditDimension[] }>("/api/audit/dimensions").then((r) => r.data),
};

export const pacingApi = {
  analysis: (projectId: string) =>
    api.get<PacingAnalysis>(`/api/projects/${projectId}/pacing`).then((r) => r.data),
};
```

- [ ] **Step 2: Create Zustand store**

```typescript
// frontend/src/lib/store.ts
import { create } from "zustand";

interface AppState {
  currentProjectId: string | null;
  sidebarOpen: boolean;
  setCurrentProject: (id: string | null) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentProjectId: null,
  sidebarOpen: true,
  setCurrentProject: (id) => set({ currentProjectId: id }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

- [ ] **Step 3: Create providers wrapper**

```tsx
// frontend/src/app/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

- [ ] **Step 4: Create layout components**

```tsx
// frontend/src/components/layout/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Map, BarChart3, Home } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Projects", icon: Home },
];

const projectNavItems = (projectId: string) => [
  { href: `/projects/${projectId}`, label: "Overview", icon: BookOpen },
  { href: `/projects/${projectId}/atlas`, label: "Atlas", icon: Map },
  { href: `/projects/${projectId}/dashboard`, label: "Dashboard", icon: BarChart3 },
];

export function Sidebar({ projectId }: { projectId?: string }) {
  const pathname = usePathname();

  const items = projectId
    ? [...navItems, ...projectNavItems(projectId)]
    : navItems;

  return (
    <aside className="w-60 border-r bg-muted/40 p-4 space-y-2">
      <h2 className="text-lg font-bold mb-4">AiWriter</h2>
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-md text-sm",
            pathname === item.href
              ? "bg-primary text-primary-foreground"
              : "hover:bg-muted"
          )}
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </Link>
      ))}
    </aside>
  );
}
```

```tsx
// frontend/src/components/layout/header.tsx
"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";

export function Header() {
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <header className="h-14 border-b flex items-center px-4 gap-4">
      <Button variant="ghost" size="icon" onClick={toggleSidebar}>
        <Menu className="h-5 w-5" />
      </Button>
      <h1 className="text-sm font-semibold">AiWriter Studio</h1>
    </header>
  );
}
```

- [ ] **Step 5: Update root layout**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AiWriter Studio",
  description: "AI Novel Writing System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <Providers>
          <div className="flex h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col overflow-hidden">
              <Header />
              <main className="flex-1 overflow-auto p-6">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Create project list page**

```tsx
// frontend/src/app/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function HomePage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: projectsApi.list,
  });

  if (isLoading) return <div className="text-muted-foreground">Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Projects</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects?.map((p) => (
          <Link key={p.id} href={`/projects/${p.id}`}>
            <Card className="hover:border-primary transition-colors cursor-pointer">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{p.title}</CardTitle>
                  <Badge variant={p.status === "active" ? "default" : "secondary"}>
                    {p.status}
                  </Badge>
                </div>
                <CardDescription>{p.genre}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
        {projects?.length === 0 && (
          <p className="text-muted-foreground col-span-full">No projects yet.</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 8: Commit**

```bash
cd /home/zipper/Projects/AiWriter
git add frontend/
git commit -m "feat(frontend): add API client, auth, layout, and project list"
```

---

## Task 13: Studio Page

**Files:**
- Create: `frontend/src/app/projects/[id]/page.tsx`
- Create: `frontend/src/app/projects/[id]/studio/[chapterId]/page.tsx`
- Create: `frontend/src/components/studio/chapter-tree.tsx`
- Create: `frontend/src/components/studio/content-viewer.tsx`
- Create: `frontend/src/components/studio/pipeline-panel.tsx`
- Create: `frontend/src/lib/ws.ts`
- Create: `frontend/src/hooks/use-websocket.ts`

- [ ] **Step 1: Create WebSocket client**

```typescript
// frontend/src/lib/ws.ts
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface PipelineEvent {
  job_run_id: string;
  event_type: "agent_start" | "agent_progress" | "agent_complete" | "agent_error" | "pipeline_complete" | "pipeline_error";
  agent_name: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export function createPipelineWS(jobRunId: string): WebSocket {
  return new WebSocket(`${WS_URL}/ws/${jobRunId}`);
}
```

```typescript
// frontend/src/hooks/use-websocket.ts
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createPipelineWS, type PipelineEvent } from "@/lib/ws";

export function usePipelineWS(jobRunId: string | null) {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!jobRunId) return;
    const ws = createPipelineWS(jobRunId);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const event: PipelineEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    };

    return () => {
      ws.close();
      setConnected(false);
    };
  }, [jobRunId]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  const reset = () => setEvents([]);

  return { events, connected, reset };
}
```

- [ ] **Step 2: Create chapter tree component**

```tsx
// frontend/src/components/studio/chapter-tree.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { volumesApi, chaptersApi, type Volume, type Chapter } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ChapterTreeProps {
  projectId: string;
  activeChapterId?: string;
}

export function ChapterTree({ projectId, activeChapterId }: ChapterTreeProps) {
  const { data: volumes } = useQuery({
    queryKey: ["volumes", projectId],
    queryFn: () => volumesApi.list(projectId),
  });

  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });

  const chaptersByVolume = (volumeId: string) =>
    chapters?.filter((c) => c.volume_id === volumeId)
      .sort((a, b) => a.sort_order - b.sort_order) || [];

  return (
    <ScrollArea className="h-full">
      <div className="p-3 space-y-4">
        {volumes?.sort((a, b) => a.sort_order - b.sort_order).map((vol) => (
          <div key={vol.id}>
            <h3 className="text-xs font-semibold text-muted-foreground mb-1">
              {vol.title}
            </h3>
            <div className="space-y-0.5">
              {chaptersByVolume(vol.id).map((ch) => (
                <Link
                  key={ch.id}
                  href={`/projects/${projectId}/studio/${ch.id}`}
                  className={cn(
                    "block px-2 py-1.5 rounded text-sm",
                    ch.id === activeChapterId
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  )}
                >
                  <span>{ch.title}</span>
                  <Badge variant="outline" className="ml-2 text-xs">
                    {ch.status}
                  </Badge>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}
```

- [ ] **Step 3: Create content viewer**

```tsx
// frontend/src/components/studio/content-viewer.tsx
"use client";

import { ScrollArea } from "@/components/ui/scroll-area";

interface ContentViewerProps {
  content: string | null;
  title: string;
}

export function ContentViewer({ content, title }: ContentViewerProps) {
  return (
    <div className="flex-1 flex flex-col">
      <div className="border-b px-4 py-2">
        <h2 className="font-semibold">{title}</h2>
      </div>
      <ScrollArea className="flex-1 p-4">
        {content ? (
          <div className="prose prose-sm max-w-none whitespace-pre-wrap">
            {content}
          </div>
        ) : (
          <p className="text-muted-foreground">No content yet.</p>
        )}
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 4: Create pipeline panel**

```tsx
// frontend/src/components/studio/pipeline-panel.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, Loader2 } from "lucide-react";
import { pipelineApi } from "@/lib/api";
import { usePipelineWS } from "@/hooks/use-websocket";

interface PipelinePanelProps {
  chapterId: string;
}

export function PipelinePanel({ chapterId }: PipelinePanelProps) {
  const [jobRunId, setJobRunId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const { events, connected } = usePipelineWS(jobRunId);

  const handleRun = async () => {
    try {
      setRunning(true);
      const result = await pipelineApi.run(chapterId);
      setJobRunId(result.job_run_id);
    } catch (err) {
      console.error("Pipeline run failed:", err);
      setRunning(false);
    }
  };

  const lastEvent = events[events.length - 1];
  const isDone = lastEvent?.event_type === "pipeline_complete" ||
                  lastEvent?.event_type === "pipeline_error";

  return (
    <div className="w-80 border-l flex flex-col">
      <div className="p-3 border-b flex items-center justify-between">
        <h3 className="font-semibold text-sm">Pipeline</h3>
        <Button
          size="sm"
          onClick={handleRun}
          disabled={running && !isDone}
        >
          {running && !isDone ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" />
          ) : (
            <Play className="h-4 w-4 mr-1" />
          )}
          Run
        </Button>
      </div>
      {connected && (
        <Badge variant="outline" className="mx-3 mt-2 w-fit">
          Connected
        </Badge>
      )}
      <ScrollArea className="flex-1 p-3">
        <div className="space-y-2">
          {events.map((e, i) => (
            <div key={i} className="text-xs border rounded p-2">
              <div className="flex items-center justify-between">
                <Badge
                  variant={
                    e.event_type === "agent_complete" ? "default" :
                    e.event_type === "agent_error" ? "destructive" : "secondary"
                  }
                >
                  {e.event_type}
                </Badge>
                <span className="text-muted-foreground">{e.agent_name}</span>
              </div>
              {e.data && Object.keys(e.data).length > 0 && (
                <pre className="mt-1 text-muted-foreground overflow-auto">
                  {JSON.stringify(e.data, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 5: Create project overview page**

```tsx
// frontend/src/app/projects/[id]/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { projectsApi, chaptersApi, entitiesApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChapterTree } from "@/components/studio/chapter-tree";
import { Sidebar } from "@/components/layout/sidebar";

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
  });

  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });

  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">{project?.title || "Loading..."}</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Chapters</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{chapters?.length || 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Entities</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{entities?.length || 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Genre</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{project?.genre || "-"}</p>
          </CardContent>
        </Card>
      </div>
      <div className="border rounded-lg h-96">
        <ChapterTree projectId={projectId} />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create Studio page**

```tsx
// frontend/src/app/projects/[id]/studio/[chapterId]/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { chaptersApi } from "@/lib/api";
import { ChapterTree } from "@/components/studio/chapter-tree";
import { ContentViewer } from "@/components/studio/content-viewer";
import { PipelinePanel } from "@/components/studio/pipeline-panel";

export default function StudioPage() {
  const params = useParams();
  const projectId = params.id as string;
  const chapterId = params.chapterId as string;

  const { data: chapter } = useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => chaptersApi.get(chapterId),
  });

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-6">
      <div className="w-56 border-r">
        <ChapterTree projectId={projectId} activeChapterId={chapterId} />
      </div>
      <ContentViewer
        title={chapter?.title || "Loading..."}
        content={chapter?.summary || null}
      />
      <PipelinePanel chapterId={chapterId} />
    </div>
  );
}
```

- [ ] **Step 7: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 8: Commit**

```bash
cd /home/zipper/Projects/AiWriter
git add frontend/
git commit -m "feat(frontend): add Studio page with chapter tree and pipeline panel"
```

---

## Task 14: Atlas Page (Entity Graph)

**Files:**
- Create: `frontend/src/app/projects/[id]/atlas/page.tsx`
- Create: `frontend/src/components/atlas/entity-graph.tsx`
- Create: `frontend/src/components/atlas/entity-detail.tsx`

- [ ] **Step 1: Create entity graph component**

```tsx
// frontend/src/components/atlas/entity-graph.tsx
"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Entity, Relationship } from "@/lib/api";

const ENTITY_COLORS: Record<string, string> = {
  character: "#3b82f6",
  location: "#10b981",
  faction: "#f59e0b",
  item: "#ef4444",
  concept: "#8b5cf6",
  power_system: "#ec4899",
};

interface EntityGraphProps {
  entities: Entity[];
  relationships: Relationship[];
  onNodeClick?: (entity: Entity) => void;
}

export function EntityGraph({ entities, relationships, onNodeClick }: EntityGraphProps) {
  const initialNodes: Node[] = useMemo(
    () =>
      entities.map((e, i) => ({
        id: e.id,
        position: {
          x: 150 + (i % 5) * 200,
          y: 100 + Math.floor(i / 5) * 150,
        },
        data: {
          label: e.name,
          entity: e,
        },
        style: {
          background: ENTITY_COLORS[e.entity_type] || "#6b7280",
          color: "white",
          border: "none",
          borderRadius: "8px",
          padding: "8px 16px",
          fontSize: "14px",
        },
      })),
    [entities]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      relationships.map((r) => ({
        id: r.id,
        source: r.source_entity_id,
        target: r.target_entity_id,
        label: r.relation_type,
        style: { stroke: "#94a3b8" },
        labelStyle: { fontSize: "11px", fill: "#64748b" },
      })),
    [relationships]
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const entity = entities.find((e) => e.id === node.id);
      if (entity && onNodeClick) onNodeClick(entity);
    },
    [entities, onNodeClick]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      fitView
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}
```

- [ ] **Step 2: Create entity detail panel**

```tsx
// frontend/src/components/atlas/entity-detail.tsx
"use client";

import type { Entity } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface EntityDetailProps {
  entity: Entity | null;
}

export function EntityDetail({ entity }: EntityDetailProps) {
  if (!entity) {
    return (
      <div className="w-80 border-l p-4 text-muted-foreground text-sm">
        Click an entity to view details.
      </div>
    );
  }

  return (
    <div className="w-80 border-l">
      <ScrollArea className="h-full">
        <div className="p-4 space-y-4">
          <div>
            <h3 className="text-lg font-bold">{entity.name}</h3>
            <Badge>{entity.entity_type}</Badge>
          </div>
          <Separator />
          {entity.description && (
            <div>
              <h4 className="text-sm font-semibold mb-1">Description</h4>
              <p className="text-sm text-muted-foreground">{entity.description}</p>
            </div>
          )}
          {entity.attributes && Object.keys(entity.attributes).length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-1">Attributes</h4>
              <Card>
                <CardContent className="p-3 text-xs">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(entity.attributes, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 3: Create Atlas page**

```tsx
// frontend/src/app/projects/[id]/atlas/page.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { entitiesApi, type Entity } from "@/lib/api";
import { EntityGraph } from "@/components/atlas/entity-graph";
import { EntityDetail } from "@/components/atlas/entity-detail";

export default function AtlasPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);

  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  const { data: relationships } = useQuery({
    queryKey: ["relationships", projectId],
    queryFn: () => entitiesApi.relationships(projectId),
  });

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-6">
      <div className="flex-1">
        <EntityGraph
          entities={entities || []}
          relationships={relationships || []}
          onNodeClick={setSelectedEntity}
        />
      </div>
      <EntityDetail entity={selectedEntity} />
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /home/zipper/Projects/AiWriter
git add frontend/
git commit -m "feat(frontend): add Atlas page with ReactFlow entity graph"
```

---

## Task 15: Dashboard Page (Audit + Pacing)

**Files:**
- Create: `frontend/src/app/projects/[id]/dashboard/page.tsx`
- Create: `frontend/src/components/dashboard/audit-radar.tsx`
- Create: `frontend/src/components/dashboard/pacing-chart.tsx`
- Create: `frontend/src/components/dashboard/stats-cards.tsx`

- [ ] **Step 1: Create stats cards**

```tsx
// frontend/src/components/dashboard/stats-cards.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { chaptersApi, entitiesApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Users, FileText, BarChart } from "lucide-react";

export function StatsCards({ projectId }: { projectId: string }) {
  const { data: chapters } = useQuery({
    queryKey: ["chapters", projectId],
    queryFn: () => chaptersApi.list(projectId),
  });
  const { data: entities } = useQuery({
    queryKey: ["entities", projectId],
    queryFn: () => entitiesApi.list(projectId),
  });

  const stats = [
    { label: "Chapters", value: chapters?.length || 0, icon: BookOpen },
    { label: "Final", value: chapters?.filter((c) => c.status === "final").length || 0, icon: FileText },
    { label: "Entities", value: entities?.length || 0, icon: Users },
    { label: "Characters", value: entities?.filter((e) => e.entity_type === "character").length || 0, icon: BarChart },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{s.label}</CardTitle>
            <s.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{s.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create audit radar chart**

```tsx
// frontend/src/components/dashboard/audit-radar.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/lib/api";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AuditRadar({ projectId }: { projectId: string }) {
  const { data: dimData } = useQuery({
    queryKey: ["audit-dimensions"],
    queryFn: auditApi.dimensions,
  });

  // Group dimensions by category for radar chart
  const categories = dimData?.dimensions?.reduce(
    (acc, dim) => {
      if (!acc[dim.category]) acc[dim.category] = 0;
      acc[dim.category]++;
      return acc;
    },
    {} as Record<string, number>
  ) || {};

  const radarData = Object.entries(categories).map(([cat, count]) => ({
    category: cat,
    dimensions: count,
    fullMark: 10,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Audit Dimensions</CardTitle>
      </CardHeader>
      <CardContent>
        {radarData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="category" />
              <PolarRadiusAxis />
              <Radar
                name="Dimensions"
                dataKey="dimensions"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.3}
              />
            </RadarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-muted-foreground text-sm">No audit data available.</p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Create pacing chart**

```tsx
// frontend/src/components/dashboard/pacing-chart.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { pacingApi } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STRAND_COLORS: Record<string, string> = {
  quest: "#3b82f6",
  fire: "#ef4444",
  constellation: "#8b5cf6",
};

export function PacingChart({ projectId }: { projectId: string }) {
  const { data: pacing } = useQuery({
    queryKey: ["pacing", projectId],
    queryFn: () => pacingApi.analysis(projectId),
  });

  const chartData = pacing?.chapters?.map((ch, i) => ({
    chapter: `Ch${i + 1}`,
    emotion: ch.emotion_level,
    strand: ch.strand,
  })) || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Pacing & Emotion Curve</CardTitle>
      </CardHeader>
      <CardContent>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="chapter" />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="emotion"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: "#3b82f6" }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-muted-foreground text-sm">No pacing data available.</p>
        )}
        {pacing?.strand_ratios && (
          <div className="mt-4 flex gap-4">
            {Object.entries(pacing.strand_ratios).map(([strand, ratio]) => (
              <div key={strand} className="text-sm">
                <span
                  className="inline-block w-3 h-3 rounded-full mr-1"
                  style={{ background: STRAND_COLORS[strand] || "#6b7280" }}
                />
                {strand}: {(ratio * 100).toFixed(0)}%
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Create Dashboard page**

```tsx
// frontend/src/app/projects/[id]/dashboard/page.tsx
"use client";

import { useParams } from "next/navigation";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { AuditRadar } from "@/components/dashboard/audit-radar";
import { PacingChart } from "@/components/dashboard/pacing-chart";

export default function DashboardPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>
      <StatsCards projectId={projectId} />
      <div className="grid gap-4 md:grid-cols-2">
        <AuditRadar projectId={projectId} />
        <PacingChart projectId={projectId} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
cd /home/zipper/Projects/AiWriter
git add frontend/
git commit -m "feat(frontend): add Dashboard page with audit radar and pacing chart"
```

---

## Task 16: Integration Tests

**Files:**
- Test: `backend/tests/test_integration_iter4.py`

- [ ] **Step 1: Write integration tests**

```python
# backend/tests/test_integration_iter4.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.embedding_service import EmbeddingService
from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
from app.engines.memory_engine import MemoryEngine
from app.engines.context_filter import ContextFilter
from app.events.event_bus import EventBus, PipelineEvent
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.memory_entry import MemoryEntry
from app.models.truth_file import TruthFile


async def _setup_integration_data(db: AsyncSession):
    project = Project(title="Integration", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    vol = Volume(project_id=project.id, title="V1", objective="o", sort_order=1)
    db.add(vol)
    await db.flush()

    pov = Entity(
        project_id=project.id, name="叶辰", entity_type="character",
        description="主角", confidence=1.0, source="manual",
        embedding=[0.5] * 1536,
    )
    db.add(pov)
    await db.flush()

    chapters = []
    for i in range(1, 8):
        ch = Chapter(
            project_id=project.id, volume_id=vol.id,
            title=f"Chapter {i}", sort_order=i,
            pov_character_id=pov.id,
            status="final" if i < 7 else "planned",
            summary=f"第{i}章发生了精彩的故事",
        )
        db.add(ch)
        await db.flush()
        chapters.append(ch)

    tf = TruthFile(
        project_id=project.id, file_type="story_bible",
        content={"world": "修仙世界"}, version=1,
    )
    tf2 = TruthFile(
        project_id=project.id, file_type="current_state",
        content={"chapter": 6}, version=1,
    )
    db.add_all([tf, tf2])
    await db.flush()
    return project, pov, chapters


async def test_rag_to_memory_flow(db_session: AsyncSession):
    """Test: create memories → embed → retrieve via RAG."""
    project, pov, chapters = await _setup_integration_data(db_session)

    mock_provider = AsyncMock()
    mock_provider.embedding.return_value = [[0.5] * 1536]
    embed_svc = EmbeddingService(db_session, mock_provider)
    mem_engine = MemoryEngine(db_session, embed_svc)

    # Create memories for first 3 chapters
    for ch in chapters[:3]:
        await mem_engine.create_memory(ch.id, ch.summary)

    # Retrieve via RAG
    rag = HybridRAGEngine(db_session, embed_svc)
    results = await rag.vector_search([0.5] * 1536, project.id, top_k=5)
    # Should find entity + memories
    assert len(results) > 0


async def test_context_filter_with_rag_integration(db_session: AsyncSession):
    """Test progressive context with RAG for late chapters."""
    project, pov, chapters = await _setup_integration_data(db_session)
    target = chapters[-1]  # Chapter 7

    with patch("app.engines.context_filter.HybridRAGEngine") as MockRAG:
        mock_rag = AsyncMock()
        MockRAG.return_value = mock_rag
        mock_rag.retrieve.return_value = [
            SearchResult("entity", uuid4(), "RAG找到了重要线索", 0.9),
        ]
        with patch("app.engines.context_filter.EmbeddingService"):
            cf = ContextFilter(db_session)
            ctx = await cf.assemble_context(target.id, pov.id)

    assert ctx["context_tokens"] > 0
    assert "rag_results" in ctx["sections"]


async def test_event_bus_roundtrip():
    """Test event serialization/deserialization roundtrip."""
    job_id = uuid4()
    events = [
        PipelineEvent(job_id, "agent_start", "radar"),
        PipelineEvent(job_id, "agent_complete", "radar", {"duration_ms": 500}),
        PipelineEvent(job_id, "agent_start", "writer"),
        PipelineEvent(job_id, "pipeline_complete", "", {"total_ms": 5000}),
    ]
    for e in events:
        restored = PipelineEvent.from_json(e.to_json())
        assert restored.event_type == e.event_type
        assert restored.agent_name == e.agent_name


async def test_full_iter4_components_exist():
    """Verify all iteration 4 components are importable."""
    from app.engines.embedding_service import EmbeddingService
    from app.engines.hybrid_rag import HybridRAGEngine, SearchResult
    from app.engines.memory_engine import MemoryEngine
    from app.events.event_bus import EventBus, PipelineEvent
    from app.api.search import router as search_router
    from app.api.memories import router as memories_router
    from app.api.ws import router as ws_router
    from app.schemas.search import SearchRequest, SearchResponse
    from app.schemas.memory import MemoryCreate, MemoryResponse

    assert EmbeddingService is not None
    assert HybridRAGEngine is not None
    assert MemoryEngine is not None
    assert EventBus is not None
```

- [ ] **Step 2: Run all tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/ -v`
Expected: All tests PASS (198 old + ~53 new)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_integration_iter4.py
git commit -m "test: add iteration 4 integration tests"
```

---

## Summary

| Task | Component | New Tests |
|------|-----------|-----------|
| 1 | RAG deps + config + HNSW | 2 |
| 2 | Embedding Service | 6 |
| 3 | Vector Search | 3 |
| 4 | BM25 Search | 2 |
| 5 | Graph + RRF + Rerank | 5 |
| 6 | Full Retrieve Pipeline | 1 |
| 7 | Memory Engine | 6 |
| 8 | Schemas + APIs | 14 |
| 9 | ContextFilter RAG | 4 |
| 10 | Event Bus + WebSocket | 9 |
| 11 | Next.js Scaffold | 0 |
| 12 | API Client + Layout | 0 |
| 13 | Studio Page | 0 |
| 14 | Atlas Page | 0 |
| 15 | Dashboard Page | 0 |
| 16 | Integration Tests | 4 |
| **Total** | | **~56** |

**Estimated total tests after iteration 4: ~254 (198 + 56)**
