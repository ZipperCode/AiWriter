# AiWriter 迭代1：项目骨架 + 数据层 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零搭建 AiWriter 后端骨架，包括 Docker 环境、全部数据库表、基础 CRUD API、LLM Provider 适配器和 Token 认证。

**Architecture:** FastAPI async 后端，SQLAlchemy 2.0 ORM + asyncpg 驱动连接 PostgreSQL 17 (pgvector)，Redis 8 作为缓存/消息总线，Alembic 管理迁移。所有 API 使用 Bearer Token 认证。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, pgvector, Redis, Docker Compose, pytest, httpx

**Spec:** `docs/superpowers/specs/2026-03-22-aiwriter-architecture-design.md` — 第一、二、五、六章

---

## File Structure

```
AiWriter/
├── docker-compose.yml
├── .env.example
├── .env                        # git ignored
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app factory
│   │   ├── config.py           # pydantic-settings
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # DeclarativeBase + UUIDMixin + TimestampMixin
│   │   │   └── session.py      # async engine + session factory
│   │   ├── models/
│   │   │   ├── __init__.py     # re-export all models
│   │   │   ├── project.py
│   │   │   ├── volume.py
│   │   │   ├── chapter.py
│   │   │   ├── draft.py
│   │   │   ├── entity.py
│   │   │   ├── relationship.py
│   │   │   ├── truth_file.py
│   │   │   ├── scene_card.py
│   │   │   ├── hook.py
│   │   │   ├── pacing_meta.py
│   │   │   ├── audit_record.py
│   │   │   ├── memory_entry.py
│   │   │   ├── worldbook.py
│   │   │   ├── style_preset.py
│   │   │   ├── book_rules.py
│   │   │   ├── outline_candidate.py
│   │   │   ├── provider_config.py
│   │   │   ├── usage_record.py
│   │   │   ├── job_run.py
│   │   │   └── workflow_preset.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── common.py       # Pagination, ErrorResponse, etc.
│   │   │   ├── project.py
│   │   │   ├── volume.py
│   │   │   ├── chapter.py
│   │   │   └── entity.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py         # get_db, get_current_user
│   │   │   ├── projects.py
│   │   │   ├── volumes.py
│   │   │   ├── chapters.py
│   │   │   └── entities.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # BaseLLMProvider ABC
│   │   │   ├── openai_compat.py
│   │   │   └── registry.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── project_service.py  # create project + init truth files
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py         # fixtures: async db, client, auth
│       ├── test_models.py
│       ├── test_api_projects.py
│       ├── test_api_volumes.py
│       ├── test_api_chapters.py
│       ├── test_api_entities.py
│       └── test_providers.py
├── frontend/                   # placeholder for iteration 4
│   └── .gitkeep
└── storage/                    # local file storage
    └── .gitkeep
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create backend/pyproject.toml**

```toml
[project]
name = "aiwriter-backend"
version = "0.1.0"
description = "AI Novel Writing System - Backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "pgvector>=0.3.6",
    "redis>=5.2.0",
    "httpx>=0.28.0",
    "cryptography>=44.0.0",
    "structlog>=24.4.0",
    "openai>=1.58.0",
    "tiktoken>=0.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: aiwriter
      POSTGRES_PASSWORD: ${DB_PASSWORD:-aiwriter_dev}
      POSTGRES_DB: aiwriter
    ports: ["5432:5432"]
    volumes: [postgres-data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aiwriter"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:8-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+asyncpg://aiwriter:${DB_PASSWORD:-aiwriter_dev}@postgres/aiwriter
      REDIS_URL: redis://redis:6379
      AUTH_TOKEN: ${AUTH_TOKEN:-dev-token-change-me}
      EMBEDDING_DIM: ${EMBEDDING_DIM:-1536}
    volumes:
      - ./backend:/app
      - ./storage:/app/storage

volumes:
  postgres-data:
```

- [ ] **Step 4: Create .env.example and .gitignore**

`.env.example`:
```
DB_PASSWORD=aiwriter_dev
AUTH_TOKEN=dev-token-change-me
EMBEDDING_DIM=1536
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
```

`.gitignore` (append to existing if any):
```
.env
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.ruff_cache/
node_modules/
.next/
storage/*
!storage/.gitkeep
```

- [ ] **Step 5: Create placeholder directories**

```bash
mkdir -p backend/app/{db,models,schemas,api,providers,services}
mkdir -p backend/tests
mkdir -p frontend storage
touch backend/app/__init__.py backend/app/db/__init__.py backend/app/models/__init__.py
touch backend/app/schemas/__init__.py backend/app/api/__init__.py
touch backend/app/providers/__init__.py backend/app/services/__init__.py
touch backend/tests/__init__.py frontend/.gitkeep storage/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure with Docker Compose"
```

---

## Task 2: FastAPI App + Config

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://aiwriter:aiwriter_dev@localhost/aiwriter"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    auth_token: str = "dev-token-change-me"

    # Embedding
    embedding_dim: int = 1536

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 2: Create main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="AiWriter API",
        version="0.1.0",
        description="AI Novel Writing System",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Verify app starts**

Run: `cd backend && pip install -e ".[dev]" && uvicorn app.main:app --port 8000 &`
Then: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/main.py
git commit -m "feat: add FastAPI app factory with config and health endpoint"
```

---

## Task 3: Database Base + Session

**Files:**
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Test: `backend/tests/conftest.py`

- [ ] **Step 1: Create db/base.py with UUID + Timestamp mixins**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Create db/session.py**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    echo=settings.debug,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 3: Create tests/conftest.py with test fixtures**

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base
from app.db.session import get_async_session
from app.main import app

# Use a separate test database or same with cleanup
TEST_DATABASE_URL = settings.database_url

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async def _override_session():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {settings.auth_token}"}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/ backend/tests/conftest.py
git commit -m "feat: add database base classes, session factory, and test fixtures"
```

---

## Task 4: Core Models — Project, Volume, Chapter, Draft

**Files:**
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/volume.py`
- Create: `backend/app/models/chapter.py`
- Create: `backend/app/models/draft.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write test for Project model**

```python
# backend/tests/test_models.py
import pytest
from sqlalchemy import select

from app.models.project import Project


async def test_create_project(db_session):
    project = Project(title="Test Novel", genre="xuanhuan", status="draft")
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.title == "Test Novel"))
    found = result.scalar_one()
    assert found.id is not None
    assert found.genre == "xuanhuan"
    assert found.created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py::test_create_project -v`
Expected: FAIL (ImportError — module not found)

- [ ] **Step 3: Implement Project model**

```python
# backend/app/models/project.py
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)  # xuanhuan/xianxia/urban/...
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    target_words: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    volumes = relationship("Volume", back_populates="project", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="project", cascade="all, delete-orphan")
    truth_files = relationship("TruthFile", back_populates="project", cascade="all, delete-orphan")
    hooks = relationship("Hook", back_populates="project", cascade="all, delete-orphan")
```

- [ ] **Step 4: Implement Volume model**

```python
# backend/app/models/volume.py
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Volume(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "volumes"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    climax_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project = relationship("Project", back_populates="volumes")
    chapters = relationship("Chapter", back_populates="volume", cascade="all, delete-orphan")
```

- [ ] **Step 5: Implement Chapter model**

```python
# backend/app/models/chapter.py
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Chapter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chapters"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    volume_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("volumes.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pov_character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id"), nullable=True
    )
    timeline_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )  # planned/writing/draft_ready/audited/final/needs_revision
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    project = relationship("Project")
    volume = relationship("Volume", back_populates="chapters")
    drafts = relationship("Draft", back_populates="chapter", cascade="all, delete-orphan")
    scene_cards = relationship("SceneCard", back_populates="chapter", cascade="all, delete-orphan")
```

- [ ] **Step 6: Implement Draft model**

```python
# backend/app/models/draft.py
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base, TimestampMixin, UUIDMixin


class Draft(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "drafts"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    audit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    content_embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)

    chapter = relationship("Chapter", back_populates="drafts")
```

- [ ] **Step 7: Update models/__init__.py and run test**

```python
# backend/app/models/__init__.py
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.draft import Draft

__all__ = ["Project", "Volume", "Chapter", "Draft"]
```

Run: `cd backend && pytest tests/test_models.py::test_create_project -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add core models — Project, Volume, Chapter, Draft"
```

---

## Task 5: World Model Tables — Entity, Relationship

**Files:**
- Create: `backend/app/models/entity.py`
- Create: `backend/app/models/relationship.py`
- Test: `backend/tests/test_models.py` (append)

- [ ] **Step 1: Write test for Entity model**

Append to `backend/tests/test_models.py`:

```python
from app.models.entity import Entity


async def test_create_entity(db_session):
    project = Project(title="Test", genre="xuanhuan", status="draft")
    db_session.add(project)
    await db_session.flush()

    entity = Entity(
        project_id=project.id,
        name="叶辰",
        entity_type="character",
        aliases=["叶少", "辰哥"],
        attributes={"personality": "冷傲"},
        source="manual",
    )
    db_session.add(entity)
    await db_session.commit()

    result = await db_session.execute(select(Entity).where(Entity.name == "叶辰"))
    found = result.scalar_one()
    assert found.aliases == ["叶少", "辰哥"]
    assert found.confidence == 1.0
```

- [ ] **Step 2: Run test → FAIL**

- [ ] **Step 3: Implement Entity model**

```python
# backend/app/models/entity.py
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base, TimestampMixin, UUIDMixin


class Entity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "entities"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # character/location/faction/item/concept/power_system
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    locked_attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    knowledge_boundary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # manual / auto_extracted

    project = relationship("Project", back_populates="entities")
```

- [ ] **Step 4: Implement Relationship model**

```python
# backend/app/models/relationship.py
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Relationship(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "relationships"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # ally/enemy/parent/lover/mentor/subordinate...
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    valid_from_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    valid_to_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )

    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])
```

- [ ] **Step 5: Update models/__init__.py, run tests → PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/entity.py backend/app/models/relationship.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat: add Entity and Relationship models for world model"
```

---

## Task 6: State/Audit Tables

**Files:**
- Create: `backend/app/models/truth_file.py`
- Create: `backend/app/models/scene_card.py`
- Create: `backend/app/models/hook.py`
- Create: `backend/app/models/pacing_meta.py`
- Create: `backend/app/models/audit_record.py`
- Create: `backend/app/models/memory_entry.py`

- [ ] **Step 1: Implement TruthFile + TruthFileHistory**

```python
# backend/app/models/truth_file.py
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TruthFile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "truth_files"
    __table_args__ = (UniqueConstraint("project_id", "file_type"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # story_bible/volume_outline/book_rules/current_state/particle_ledger
    # pending_hooks/chapter_summaries/subplot_board/emotional_arcs/character_matrix
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )

    project = relationship("Project", back_populates="truth_files")
    history = relationship(
        "TruthFileHistory", back_populates="truth_file", cascade="all, delete-orphan"
    )


class TruthFileHistory(Base, UUIDMixin):
    __tablename__ = "truth_file_history"

    truth_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("truth_files.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_by_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id"), nullable=True
    )
    created_at = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True),
        server_default=__import__("sqlalchemy").func.now(),
        nullable=False,
    )

    truth_file = relationship("TruthFile", back_populates="history")
```

- [ ] **Step 2: Implement SceneCard, Hook, PacingMeta, AuditRecord, MemoryEntry**

Each follows the same pattern — see spec 1.4 for fields. Create one file per model:

`scene_card.py` — chapter_id, pov_character_id, location, time_marker, goal, conflict, outcome, characters(JSONB), notes, sort_order
`hook.py` — project_id, hook_type, description, planted_chapter_id, expected_resolve_chapter, resolved_chapter_id, status
`pacing_meta.py` — chapter_id(UNIQUE), quest_ratio, fire_ratio, constellation_ratio, highlight_count, highlight_types(JSONB), tension_level, strand_tags(JSONB)
`audit_record.py` — chapter_id, draft_id, dimension, category, score(Float), severity, message, evidence(JSONB)
`memory_entry.py` — chapter_id, summary(Text), embedding(Vector)

- [ ] **Step 3: Update models/__init__.py with all new models**

- [ ] **Step 4: Write quick smoke test to ensure all tables create**

```python
# append to backend/tests/test_models.py
from app.models import (
    TruthFile, SceneCard, Hook, PacingMeta, AuditRecord, MemoryEntry
)

async def test_all_state_tables_exist(db_session):
    """Smoke test: all state/audit tables are created without errors."""
    # The setup_db fixture creates all tables; just verify no exceptions
    assert True
```

Run: `pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add state/audit models — TruthFile, SceneCard, Hook, PacingMeta, AuditRecord, MemoryEntry"
```

---

## Task 7: Supplementary + Global Tables

**Files:**
- Create: `backend/app/models/worldbook.py`
- Create: `backend/app/models/style_preset.py`
- Create: `backend/app/models/book_rules.py`
- Create: `backend/app/models/outline_candidate.py`
- Create: `backend/app/models/provider_config.py`
- Create: `backend/app/models/usage_record.py`
- Create: `backend/app/models/job_run.py`
- Create: `backend/app/models/workflow_preset.py`

- [ ] **Step 1: Implement all 8 remaining models**

Each model follows UUIDMixin + TimestampMixin pattern. Key fields per spec:

- `worldbook.py` — project_id, title, category, content(Text), tags(JSONB)
- `style_preset.py` — project_id(nullable, for global presets), name, description, prompt_content(Text), settings(JSONB)
- `book_rules.py` — project_id, base_guardrails(JSONB), genre_profile(JSONB), custom_rules(JSONB)
- `outline_candidate.py` — project_id, stage(String), content(JSONB), selected(Boolean)
- `provider_config.py` — name, provider_type, base_url, api_key_encrypted(String), default_model, settings(JSONB), is_active(Boolean)
- `usage_record.py` — provider_config_id, model, input_tokens, output_tokens, cost, agent_name, job_run_id
- `job_run.py` — project_id, job_type, status, agent_chain(JSONB), result(JSONB), error_message, started_at, finished_at
- `workflow_preset.py` — name, description, dag_config(JSONB), human_loop_config(JSONB)

Note: `provider_config.api_key_encrypted` uses Fernet encryption — store encrypted string, decrypt at runtime.

- [ ] **Step 2: Update models/__init__.py with all 20 models**

- [ ] **Step 3: Run full test suite → all PASS**

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add supplementary and global models — complete all 20 database tables"
```

---

## Task 8: Alembic Setup + Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/app/db/migrations/env.py`
- Create: `backend/app/db/migrations/versions/` (auto-generated)

- [ ] **Step 1: Initialize Alembic**

```bash
cd backend && alembic init app/db/migrations
```

- [ ] **Step 2: Edit alembic.ini**

Set `sqlalchemy.url` to empty (we'll override in env.py):

```ini
# line: sqlalchemy.url = ...
sqlalchemy.url =
```

- [ ] **Step 3: Edit migrations/env.py for async + import all models**

Key changes to `app/db/migrations/env.py`:
- Import `app.config.settings` for DATABASE_URL
- Import `app.db.base.Base` for metadata
- Import `app.models` to register all models
- Use `run_async_migrations()` with `create_async_engine`

```python
# Replace the entire env.py with async version
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.base import Base
import app.models  # noqa: F401 — register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Requires running PostgreSQL (use Docker):

```bash
docker compose up -d postgres
sleep 3
cd backend && alembic revision --autogenerate -m "initial schema - all 20 tables"
```

- [ ] **Step 5: Apply migration**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 6: Verify tables exist**

```bash
docker compose exec postgres psql -U aiwriter -c "\dt"
```
Expected: All 20+ tables listed

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/app/db/migrations/
git commit -m "feat: add Alembic migration setup with initial schema"
```

---

## Task 9: Token Auth + API Dependencies

**Files:**
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing test for auth**

```python
# backend/tests/test_auth.py
async def test_health_no_auth(client):
    """Health endpoint should work without auth."""
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_protected_endpoint_no_token(client):
    """Protected endpoints should return 401 without token."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


async def test_protected_endpoint_wrong_token(client):
    """Protected endpoints should return 401 with wrong token."""
    resp = await client.get("/api/projects", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


async def test_protected_endpoint_valid_token(client, auth_headers):
    """Protected endpoints should return 200 with valid token."""
    resp = await client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement deps.py**

```python
# backend/app/api/deps.py
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_async_session

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    if credentials.credentials != settings.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return credentials.credentials
```

- [ ] **Step 4: Create minimal projects router to test auth (will be expanded in Task 10)**

```python
# backend/app/api/projects.py
from fastapi import APIRouter, Depends

from app.api.deps import verify_token

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(verify_token)])


@router.get("")
async def list_projects():
    return {"items": [], "total": 0}
```

Register router in `main.py`:
```python
# In create_app(), before return:
from app.api.projects import router as projects_router
app.include_router(projects_router)
```

- [ ] **Step 5: Run tests → PASS**

Run: `cd backend && pytest tests/test_auth.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/app/api/projects.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add Bearer token auth and API dependencies"
```

---

## Task 10: Pydantic Schemas + Projects CRUD API

**Files:**
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/services/project_service.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/test_api_projects.py`

- [ ] **Step 1: Write failing tests for project CRUD**

```python
# backend/tests/test_api_projects.py
import pytest


async def test_create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects",
        json={"title": "仙侠奇缘", "genre": "xianxia"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "仙侠奇缘"
    assert data["genre"] == "xianxia"
    assert "id" in data


async def test_list_projects(client, auth_headers):
    # Create two projects first
    await client.post("/api/projects", json={"title": "P1", "genre": "xuanhuan"}, headers=auth_headers)
    await client.post("/api/projects", json={"title": "P2", "genre": "urban"}, headers=auth_headers)

    resp = await client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


async def test_get_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "Get Test", "genre": "horror"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Test"


async def test_update_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "Old Title", "genre": "scifi"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.put(
        f"/api/projects/{pid}",
        json={"title": "New Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


async def test_delete_project(client, auth_headers):
    create_resp = await client.post(
        "/api/projects",
        json={"title": "To Delete", "genre": "romance"},
        headers=auth_headers,
    )
    pid = create_resp.json()["id"]

    resp = await client.delete(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests → FAIL**

- [ ] **Step 3: Implement schemas**

```python
# backend/app/schemas/common.py
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    error: dict  # {"code": str, "message": str, "details": any}
```

```python
# backend/app/schemas/project.py
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
```

- [ ] **Step 4: Implement project service (create project + init 10 truth files)**

```python
# backend/app/services/project_service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.truth_file import TruthFile
from app.schemas.project import ProjectCreate

TRUTH_FILE_TYPES = [
    "story_bible",
    "volume_outline",
    "book_rules",
    "current_state",
    "particle_ledger",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "character_matrix",
]


async def create_project_with_truth_files(
    db: AsyncSession, data: ProjectCreate
) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()

    # Initialize 10 truth files
    for file_type in TRUTH_FILE_TYPES:
        truth_file = TruthFile(
            project_id=project.id,
            file_type=file_type,
            content={},
            version=1,
        )
        db.add(truth_file)

    await db.flush()
    return project
```

- [ ] **Step 5: Implement full projects router**

```python
# backend/app/api/projects.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import create_project_with_truth_files

router = APIRouter(
    prefix="/api/projects", tags=["projects"], dependencies=[Depends(verify_token)]
)


@router.get("", response_model=dict)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_q = await db.execute(select(func.count(Project.id)))
    total = total_q.scalar_one()
    q = select(Project).offset((page - 1) * page_size).limit(page_size).order_by(Project.created_at.desc())
    result = await db.execute(q)
    items = [ProjectResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = await create_project_with_truth_files(db, data)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
```

- [ ] **Step 6: Run tests → PASS**

Run: `cd backend && pytest tests/test_api_projects.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/ backend/app/services/ backend/app/api/projects.py backend/tests/test_api_projects.py
git commit -m "feat: add Projects CRUD API with truth file initialization"
```

---

## Task 11: Volumes CRUD API

**Files:**
- Create: `backend/app/schemas/volume.py`
- Create: `backend/app/api/volumes.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_api_volumes.py`

- [ ] **Step 1: Write failing tests**

Same CRUD pattern as projects, but scoped to `/api/projects/{id}/volumes`. Test create, list, get, update, delete.

- [ ] **Step 2: Implement VolumeCreate/VolumeUpdate/VolumeResponse schemas**

- [ ] **Step 3: Implement volumes router — same pattern as projects, but with project_id scoping**

- [ ] **Step 4: Register router in main.py**

- [ ] **Step 5: Run tests → PASS, commit**

```bash
git commit -m "feat: add Volumes CRUD API"
```

---

## Task 12: Chapters CRUD API

**Files:**
- Create: `backend/app/schemas/chapter.py`
- Create: `backend/app/api/chapters.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_chapters.py`

- [ ] **Step 1: Write failing tests**

Endpoints: `POST /api/projects/{id}/chapters`, `GET /api/projects/{id}/chapters?volume_id=`, `GET /api/chapters/{id}`, `PUT /api/chapters/{id}`

- [ ] **Step 2: Implement schemas**

- [ ] **Step 3: Implement chapters router**

- [ ] **Step 4: Register router, run tests → PASS, commit**

```bash
git commit -m "feat: add Chapters CRUD API"
```

---

## Task 13: Entities CRUD API

**Files:**
- Create: `backend/app/schemas/entity.py`
- Create: `backend/app/api/entities.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_entities.py`

- [ ] **Step 1: Write failing tests**

Endpoints: `POST /api/projects/{id}/entities`, `GET /api/projects/{id}/entities?entity_type=`, `PUT /api/entities/{id}`, `POST /api/projects/{id}/relationships`, `GET /api/projects/{id}/relationships`

- [ ] **Step 2: Implement EntityCreate/EntityResponse + RelationshipCreate/RelationshipResponse schemas**

- [ ] **Step 3: Implement entities router (including relationship endpoints)**

- [ ] **Step 4: Register router, run tests → PASS, commit**

```bash
git commit -m "feat: add Entities and Relationships CRUD API"
```

---

## Task 14: LLM Provider Base + OpenAI Compatible Implementation

**Files:**
- Create: `backend/app/providers/base.py`
- Create: `backend/app/providers/openai_compat.py`
- Create: `backend/app/providers/registry.py`
- Test: `backend/tests/test_providers.py`

- [ ] **Step 1: Write tests for provider**

```python
# backend/tests/test_providers.py
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.base import BaseLLMProvider, ChatResponse, ChatMessage
from app.providers.openai_compat import OpenAICompatProvider
from app.providers.registry import ProviderRegistry


def test_provider_registry():
    registry = ProviderRegistry()
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    registry.register("test", provider)
    assert registry.get("test") is provider


def test_provider_registry_unknown():
    registry = ProviderRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


async def test_openai_provider_chat_mock():
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    mock_response = ChatResponse(
        content="Hello!",
        model="gpt-4o",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    with patch.object(provider, "chat", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="gpt-4o",
        )
        assert result.content == "Hello!"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement base.py**

```python
# backend/app/providers/base.py
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel


@dataclass
class ChatMessage:
    role: str  # system/user/assistant
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: Any = None


@dataclass
class ChatChunk:
    content: str
    finished: bool = False


class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[ChatChunk]: ...

    @abstractmethod
    async def structured_output(
        self,
        messages: list[ChatMessage],
        model: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
    ) -> BaseModel: ...

    @abstractmethod
    async def embedding(
        self, texts: list[str], model: str = "text-embedding-3-large"
    ) -> list[list[float]]: ...

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
```

- [ ] **Step 4: Implement openai_compat.py**

```python
# backend/app/providers/openai_compat.py
import json
from collections.abc import AsyncIterator
from typing import Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.providers.base import (
    BaseLLMProvider,
    ChatChunk,
    ChatMessage,
    ChatResponse,
)


class OpenAICompatProvider(BaseLLMProvider):
    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        resp = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        return ChatResponse(
            content=choice.message.content or "",
            model=resp.model,
            usage={
                "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
            raw=resp,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[ChatChunk]:
        stream = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield ChatChunk(content=delta.content)
        yield ChatChunk(content="", finished=True)

    async def structured_output(
        self,
        messages: list[ChatMessage],
        model: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
    ) -> BaseModel:
        schema = output_schema.model_json_schema()
        resp = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return output_schema.model_validate_json(content)

    async def embedding(
        self, texts: list[str], model: str = "text-embedding-3-large"
    ) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in resp.data]
```

- [ ] **Step 5: Implement registry.py**

```python
# backend/app/providers/registry.py
from app.providers.base import BaseLLMProvider


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseLLMProvider] = {}

    def register(self, name: str, provider: BaseLLMProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> BaseLLMProvider:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        return self._providers[name]

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())
```

- [ ] **Step 6: Run tests → PASS**

Run: `cd backend && pytest tests/test_providers.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/providers/ backend/tests/test_providers.py
git commit -m "feat: add LLM Provider base class and OpenAI-compatible implementation"
```

---

## Task 15: Docker Compose Full Integration Test

**Files:**
- None new — verify existing setup

- [ ] **Step 1: Start all services**

```bash
cp .env.example .env
docker compose up -d
```

- [ ] **Step 2: Wait for health and run migration**

```bash
docker compose exec backend alembic upgrade head
```

- [ ] **Step 3: Test API through Docker**

```bash
# Health
curl http://localhost:8000/health

# Create project (with auth)
curl -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer dev-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{"title": "测试小说", "genre": "xuanhuan"}'

# List projects
curl http://localhost:8000/api/projects \
  -H "Authorization: Bearer dev-token-change-me"
```

Expected: All return valid JSON responses

- [ ] **Step 4: Verify pgvector extension**

```bash
docker compose exec postgres psql -U aiwriter -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Expected: Shows `vector` extension

- [ ] **Step 5: Commit any docker/config fixes if needed**

```bash
git commit -m "chore: verify Docker Compose full integration"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Project Scaffolding | 15 min |
| 2 | FastAPI App + Config | 10 min |
| 3 | Database Base + Session + Test Fixtures | 15 min |
| 4 | Core Models (Project/Volume/Chapter/Draft) | 25 min |
| 5 | World Model Tables (Entity/Relationship) | 20 min |
| 6 | State/Audit Tables (6 models) | 25 min |
| 7 | Supplementary + Global Tables (8 models) | 25 min |
| 8 | Alembic Setup + Initial Migration | 15 min |
| 9 | Token Auth + API Dependencies | 15 min |
| 10 | Projects CRUD API (schemas + service + router) | 30 min |
| 11 | Volumes CRUD API | 20 min |
| 12 | Chapters CRUD API | 20 min |
| 13 | Entities CRUD API | 25 min |
| 14 | LLM Provider Base + OpenAI Compatible | 30 min |
| 15 | Docker Compose Full Integration Test | 15 min |
| **Total** | | **~5 hours** |
