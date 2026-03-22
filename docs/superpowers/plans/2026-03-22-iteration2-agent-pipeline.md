# Iteration 2: Core Agent Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete agent pipeline infrastructure — 7 agents, DAG executor, Celery task queue, and domain engines (world model + context filter + state manager) — enabling end-to-end chapter generation.

**Architecture:** Bottom-up approach: schemas → base class → domain engines → individual agents → pipeline orchestrator → Celery integration → API endpoints. All LLM calls go through the existing `BaseLLMProvider` + `OpenAICompatProvider`. Tests mock LLM responses.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Celery + Redis, jieba, pyahocorasick, pytest-asyncio

**Existing codebase (from Iteration 1):**
- 21 DB models in `backend/app/models/` (Project, Volume, Chapter, Draft, Entity, Relationship, TruthFile, TruthFileHistory, SceneCard, Hook, PacingMeta, AuditRecord, MemoryEntry, etc.)
- CRUD APIs in `backend/app/api/` (projects, volumes, chapters, entities)
- LLM providers in `backend/app/providers/` (BaseLLMProvider ABC, OpenAICompatProvider, ProviderRegistry)
- Auth in `backend/app/api/deps.py` (Bearer token)
- Config in `backend/app/config.py` (pydantic-settings)
- DB session in `backend/app/db/session.py` (async engine + session factory)
- Tests in `backend/tests/` (conftest.py with NullPool + test DB override, 6 test files, 25 tests)
- Docker: postgres:5432 + redis:6379

**Test environment:**
```bash
cd backend && source .venv/bin/activate
export DATABASE_URL="postgresql+asyncpg://aiwriter:aiwriter_dev@localhost:5432/aiwriter"
pytest tests/ -v
```

**Note on iteration 2 scope:**
- Auditor and Reviser agents are **basic framework versions** — full 33-dimension audit and 5-mode revision come in iteration 3
- Pacing Controller and De-AI Engine are **not** in this iteration (iteration 3)
- RAG engine is **not** in this iteration (iteration 4)
- ContextAgent assembles context from DB only (no RAG retrieval yet)

---

### Task 1: Add Dependencies + Create Directory Structure

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/engines/__init__.py`
- Create: `backend/app/orchestration/__init__.py`
- Create: `backend/app/jobs/__init__.py`

- [ ] **Step 1: Add new dependencies to pyproject.toml**

Add these to the `dependencies` list in `backend/pyproject.toml`:

```toml
"celery[redis]>=5.4.0",
"jieba>=0.42.1",
"pyahocorasick>=2.1.1",
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && source .venv/bin/activate && pip install -e ".[dev]"`

- [ ] **Step 3: Create empty `__init__.py` files for new packages**

Create these files (all empty):
- `backend/app/agents/__init__.py`
- `backend/app/engines/__init__.py`
- `backend/app/orchestration/__init__.py`
- `backend/app/jobs/__init__.py`

- [ ] **Step 4: Verify imports work**

Run: `cd backend && python -c "import celery; import jieba; import ahocorasick; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Verify existing tests still pass**

Run: `cd backend && source .venv/bin/activate && export DATABASE_URL="postgresql+asyncpg://aiwriter:aiwriter_dev@localhost:5432/aiwriter" && pytest tests/ -v`
Expected: 25 passed

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/agents/__init__.py backend/app/engines/__init__.py backend/app/orchestration/__init__.py backend/app/jobs/__init__.py
git commit -m "feat(iter2): add agent pipeline dependencies and directory structure"
```

---

### Task 2: Agent Schemas (Pydantic Models)

**Files:**
- Create: `backend/app/schemas/agent.py`
- Create: `backend/tests/test_agent_schemas.py`

These schemas define the input/output contracts for all agents and the pipeline.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_schemas.py
from uuid import uuid4

from app.schemas.agent import (
    AgentContext,
    AgentName,
    AgentResult,
    ArchitectInput,
    ArchitectOutput,
    AuditorInput,
    AuditorOutput,
    ContextInput,
    ContextOutput,
    PipelineNodeStatus,
    RadarInput,
    RadarOutput,
    ReviserInput,
    ReviserOutput,
    SettlerInput,
    SettlerOutput,
    ValidationIssue,
    WriterInput,
    WriterOutput,
)


def test_agent_name_enum():
    assert AgentName.RADAR == "radar"
    assert AgentName.WRITER == "writer"
    assert len(AgentName) == 7


def test_agent_context_defaults():
    ctx = AgentContext(project_id=uuid4())
    assert ctx.chapter_id is None
    assert ctx.pipeline_data == {}
    assert ctx.params == {}


def test_agent_result_success():
    r = AgentResult(agent_name="radar", success=True, data={"next": "write"})
    assert r.success is True
    assert r.error is None
    assert r.duration_ms == 0


def test_agent_result_failure():
    r = AgentResult(agent_name="writer", success=False, error="LLM timeout")
    assert r.success is False
    assert r.error == "LLM timeout"


def test_validation_issue():
    v = ValidationIssue(field="content", message="too short")
    assert v.severity == "warning"


def test_radar_schemas():
    pid = uuid4()
    inp = RadarInput(project_id=pid)
    assert inp.current_chapter_id is None

    out = RadarOutput(next_action="write_chapter", reasoning="chapter 1 planned")
    assert out.target_chapter_id is None


def test_architect_schemas():
    inp = ArchitectInput(project_id=uuid4(), stage="chapter_plan")
    out = ArchitectOutput(stage="chapter_plan", content={"chapters": []})
    assert out.stage == "chapter_plan"


def test_context_schemas():
    inp = ContextInput(chapter_id=uuid4())
    out = ContextOutput(system_prompt="You are a writer.", context_tokens=500)
    assert out.assembled_sections == {}


def test_writer_schemas():
    inp = WriterInput(chapter_id=uuid4(), target_words=3000)
    out = WriterOutput(phase1_content="Once upon a time...", word_count=4)
    assert out.phase2_settlement == {}


def test_settler_schemas():
    inp = SettlerInput(chapter_id=uuid4(), content="story text")
    out = SettlerOutput(extracted_entities=[{"name": "Hero", "type": "character"}])
    assert len(out.extracted_entities) == 1


def test_auditor_schemas():
    inp = AuditorInput(chapter_id=uuid4(), draft_id=uuid4())
    assert inp.mode == "full"
    out = AuditorOutput(pass_rate=0.9, recommendation="pass")
    assert out.has_blocking is False


def test_reviser_schemas():
    inp = ReviserInput(chapter_id=uuid4(), draft_id=uuid4())
    assert inp.mode == "polish"
    out = ReviserOutput(revised_content="Revised text", word_count=2)
    assert out.changes_summary == ""


def test_pipeline_node_status():
    assert PipelineNodeStatus.PENDING == "pending"
    assert PipelineNodeStatus.COMPLETED == "completed"
    assert PipelineNodeStatus.FAILED == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_schemas.py -v`
Expected: FAIL (ImportError — module not found)

- [ ] **Step 3: Implement agent schemas**

```python
# backend/app/schemas/agent.py
"""Schemas for the agent pipeline: input/output contracts for all agents."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# --- Enums ---

class AgentName(str, Enum):
    RADAR = "radar"
    ARCHITECT = "architect"
    CONTEXT = "context"
    WRITER = "writer"
    SETTLER = "settler"
    AUDITOR = "auditor"
    REVISER = "reviser"


class PipelineNodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_HUMAN = "waiting_human"


# --- Core pipeline types ---

class AgentContext(BaseModel):
    """Input context passed to an agent during pipeline execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_id: UUID
    chapter_id: UUID | None = None
    volume_id: UUID | None = None
    pipeline_data: dict[str, Any] = {}
    params: dict[str, Any] = {}


class AgentResult(BaseModel):
    """Output from an agent execution."""
    agent_name: str
    success: bool
    data: dict[str, Any] = {}
    error: str | None = None
    usage: dict[str, Any] = {}
    duration_ms: int = 0


class ValidationIssue(BaseModel):
    """A validation issue found in agent output."""
    field: str
    message: str
    severity: str = "warning"  # warning / error


# --- Radar Agent ---

class RadarInput(BaseModel):
    project_id: UUID
    current_chapter_id: UUID | None = None


class RadarOutput(BaseModel):
    next_action: str  # write_chapter / plan_volume / plan_chapters / done
    target_chapter_id: UUID | None = None
    target_volume_id: UUID | None = None
    reasoning: str = ""


# --- Architect Agent ---

class ArchitectInput(BaseModel):
    project_id: UUID
    stage: str  # plot_blueprint / volume_outline / chapter_plan / scene_cards
    volume_id: UUID | None = None
    chapter_id: UUID | None = None


class ArchitectOutput(BaseModel):
    stage: str
    content: dict[str, Any]


# --- Context Agent ---

class ContextInput(BaseModel):
    chapter_id: UUID
    pov_character_id: UUID | None = None


class ContextOutput(BaseModel):
    system_prompt: str = ""
    user_prompt: str = ""
    context_tokens: int = 0
    assembled_sections: dict[str, str] = {}


# --- Writer Agent ---

class WriterInput(BaseModel):
    chapter_id: UUID
    context: ContextOutput | None = None
    target_words: int = 3000


class WriterOutput(BaseModel):
    phase1_content: str
    phase2_settlement: dict[str, Any] = {}
    word_count: int = 0


# --- Settler Agent ---

class SettlerInput(BaseModel):
    chapter_id: UUID
    content: str
    settlement: dict[str, Any] = {}


class SettlerOutput(BaseModel):
    extracted_entities: list[dict[str, Any]] = []
    truth_file_updates: dict[str, Any] = {}


# --- Auditor Agent ---

class AuditorInput(BaseModel):
    chapter_id: UUID
    draft_id: UUID
    mode: str = "full"  # full / incremental / quick


class AuditorOutput(BaseModel):
    scores: dict[str, float] = {}
    pass_rate: float = 0.0
    has_blocking: bool = False
    issues: list[dict[str, Any]] = []
    recommendation: str = "pass"  # pass / revise / rework


# --- Reviser Agent ---

class ReviserInput(BaseModel):
    chapter_id: UUID
    draft_id: UUID
    mode: str = "polish"  # polish / rewrite / rework / spot-fix / anti-detect
    audit_issues: list[dict[str, Any]] = []


class ReviserOutput(BaseModel):
    revised_content: str = ""
    changes_summary: str = ""
    word_count: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_schemas.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/agent.py backend/tests/test_agent_schemas.py
git commit -m "feat(iter2): add agent pipeline Pydantic schemas"
```

---

### Task 3: BaseAgent Base Class

**Files:**
- Create: `backend/app/agents/base.py`
- Create: `backend/tests/test_base_agent.py`

The BaseAgent provides: LLM integration, retry with exponential backoff, output validation, timing.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_base_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.agents.base import BaseAgent
from app.providers.base import BaseLLMProvider, ChatMessage, ChatResponse
from app.schemas.agent import AgentContext, AgentResult, ValidationIssue


class StubAgent(BaseAgent):
    """A concrete agent for testing the base class."""

    name = "stub"
    description = "Test stub agent"
    temperature = 0.5

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        return [
            ChatMessage(role="system", content="You are a stub."),
            ChatMessage(role="user", content="Do something."),
        ]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext):
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        return {"content": resp.content}


class FailOnceAgent(BaseAgent):
    """Agent that fails on first attempt, succeeds on second."""

    name = "fail_once"
    description = "Fails once then succeeds"
    max_retries = 3

    def __init__(self, provider, model="gpt-4o"):
        super().__init__(provider, model)
        self.attempt_count = 0

    async def build_messages(self, context):
        return [ChatMessage(role="user", content="test")]

    async def _call_llm(self, messages, context):
        self.attempt_count += 1
        if self.attempt_count == 1:
            raise ValueError("Simulated LLM failure")
        return {"result": "ok"}

    async def on_retry(self, error, attempt):
        pass  # no wait in tests


class ValidatingAgent(BaseAgent):
    """Agent that always fails validation."""

    name = "validating"
    description = "Tests validation"

    async def build_messages(self, context):
        return [ChatMessage(role="user", content="test")]

    async def _call_llm(self, messages, context):
        return {"content": ""}

    async def validate_output(self, result):
        return [ValidationIssue(field="content", message="empty", severity="error")]

    async def on_retry(self, error, attempt):
        pass


def _make_mock_provider() -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(content="Hello!", model="gpt-4o", usage={"input_tokens": 10, "output_tokens": 5})
    )
    return provider


async def test_base_agent_execute_success():
    provider = _make_mock_provider()
    agent = StubAgent(provider=provider, model="gpt-4o")
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.agent_name == "stub"
    assert result.data["content"] == "Hello!"
    assert result.duration_ms >= 0
    assert result.error is None


async def test_base_agent_retry_on_failure():
    provider = _make_mock_provider()
    agent = FailOnceAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is True
    assert agent.attempt_count == 2


async def test_base_agent_all_retries_exhausted():
    provider = _make_mock_provider()
    agent = FailOnceAgent(provider=provider)
    agent.max_retries = 1  # only 1 attempt
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is False
    assert "Simulated LLM failure" in result.error


async def test_base_agent_validation_triggers_retry():
    provider = _make_mock_provider()
    agent = ValidatingAgent(provider=provider)
    agent.max_retries = 2
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    # Last attempt: validation still fails but we return success=True on last attempt
    # because the agent completed (just with validation issues)
    assert result.success is True
    assert result.agent_name == "validating"


async def test_base_agent_attributes():
    provider = _make_mock_provider()
    agent = StubAgent(provider=provider, model="claude-3")
    assert agent.name == "stub"
    assert agent.model == "claude-3"
    assert agent.temperature == 0.5
    assert agent.max_retries == 3
    assert agent.timeout_seconds == 120


async def test_base_agent_timeout():
    """Agent should fail when _call_llm exceeds timeout_seconds."""
    import asyncio

    class SlowAgent(BaseAgent):
        name = "slow"
        timeout_seconds = 1  # 1 second timeout
        max_retries = 1

        async def build_messages(self, context):
            return [ChatMessage(role="user", content="test")]

        async def _call_llm(self, messages, context):
            await asyncio.sleep(5)  # takes 5 seconds
            return {"result": "ok"}

    provider = _make_mock_provider()
    agent = SlowAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is False
    assert "timed out" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_base_agent.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement BaseAgent**

```python
# backend/app/agents/base.py
"""Base class for all agents in the pipeline."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.providers.base import BaseLLMProvider, ChatMessage
from app.schemas.agent import AgentContext, AgentResult, ValidationIssue


class BaseAgent(ABC):
    """Abstract base class for pipeline agents.

    Provides: LLM integration via provider, retry with exponential backoff,
    output validation, execution timing, and optional schema-based auto-validation.
    """

    name: str = ""
    description: str = ""
    system_prompt_template: str = ""
    input_schema: Type[BaseModel] | None = None
    output_schema: Type[BaseModel] | None = None
    temperature: float = 0.7
    max_retries: int = 3
    timeout_seconds: int = 120

    def __init__(self, provider: BaseLLMProvider, model: str = "gpt-4o"):
        self.provider = provider
        self.model = model

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute the agent with retry logic and optional timeout."""
        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                messages = await self.build_messages(context)
                raw_result = await asyncio.wait_for(
                    self._call_llm(messages, context),
                    timeout=self.timeout_seconds,
                )

                # Auto-validate with output_schema if set
                if self.output_schema and isinstance(raw_result, dict):
                    raw_result = self.output_schema(**raw_result).model_dump()

                # Custom validation
                issues = await self.validate_output(raw_result)
                blocking = [i for i in issues if i.severity == "error"]
                if blocking and attempt < self.max_retries:
                    raise ValueError(
                        f"Validation failed: {[i.message for i in blocking]}"
                    )

                elapsed = int((time.monotonic() - start) * 1000)
                data = self._to_dict(raw_result)
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    data=data,
                    duration_ms=elapsed,
                )
            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"{self.name} timed out after {self.timeout_seconds}s"
                )
                if attempt < self.max_retries:
                    await self.on_retry(last_error, attempt)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await self.on_retry(e, attempt)

        elapsed = int((time.monotonic() - start) * 1000)
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=str(last_error),
            duration_ms=elapsed,
        )

    @abstractmethod
    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        """Build the message list for the LLM call."""
        ...

    @abstractmethod
    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        """Make the actual LLM call and parse the response."""
        ...

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        """Validate agent output. Override for custom validation."""
        return []

    async def on_retry(self, error: Exception, attempt: int) -> None:
        """Called before retry. Default: exponential backoff."""
        wait = min(2**attempt, 30)
        await asyncio.sleep(wait)

    @staticmethod
    def _to_dict(result: Any) -> dict[str, Any]:
        """Convert result to dict for AgentResult.data."""
        if isinstance(result, dict):
            return result
        if isinstance(result, BaseModel):
            return result.model_dump()
        return {"raw": str(result)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_base_agent.py -v`
Expected: 5 passed

- [ ] **Step 5: Run all tests**

Run: `cd backend && pytest tests/ -v`
Expected: 30 passed (25 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/base.py backend/tests/test_base_agent.py
git commit -m "feat(iter2): implement BaseAgent with retry and validation"
```

---

### Task 4: State Manager Engine

**Files:**
- Create: `backend/app/engines/state_manager.py`
- Create: `backend/tests/test_state_manager.py`

State Manager handles truth file CRUD with atomic version increment + history logging.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_state_manager.py
import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.state_manager import StateManager
from app.models.project import Project
from app.models.truth_file import TruthFile, TruthFileHistory


async def _create_project(db: AsyncSession) -> Project:
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    # Create a truth file
    tf = TruthFile(
        project_id=project.id,
        file_type="current_state",
        content={"chapter": 0, "characters": []},
        version=1,
    )
    db.add(tf)
    await db.flush()
    return project


async def test_get_truth_file(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)

    tf = await mgr.get_truth_file(project.id, "current_state")
    assert tf is not None
    assert tf.file_type == "current_state"
    assert tf.version == 1


async def test_get_truth_file_not_found(db_session: AsyncSession):
    mgr = StateManager(db_session)
    tf = await mgr.get_truth_file(uuid4(), "current_state")
    assert tf is None


async def test_update_truth_file(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)
    chapter_id = uuid4()

    updated = await mgr.update_truth_file(
        project.id,
        "current_state",
        diff={"chapter": 1, "characters": ["Hero"]},
        chapter_id=chapter_id,
    )

    assert updated.version == 2
    assert updated.content["chapter"] == 1
    assert updated.content["characters"] == ["Hero"]


async def test_update_creates_history(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)

    await mgr.update_truth_file(
        project.id, "current_state", diff={"chapter": 1}, chapter_id=None
    )

    history = await mgr.get_history(project.id, "current_state")
    assert len(history) == 1
    assert history[0].version == 1  # previous version saved
    assert history[0].content == {"chapter": 0, "characters": []}


async def test_get_truth_file_at_version(db_session: AsyncSession):
    project = await _create_project(db_session)
    mgr = StateManager(db_session)

    await mgr.update_truth_file(
        project.id, "current_state", diff={"chapter": 1}, chapter_id=None
    )
    await mgr.update_truth_file(
        project.id, "current_state", diff={"chapter": 2}, chapter_id=None
    )

    v1 = await mgr.get_truth_file_at_version(project.id, "current_state", 1)
    assert v1 is not None
    assert v1.content == {"chapter": 0, "characters": []}

    v2 = await mgr.get_truth_file_at_version(project.id, "current_state", 2)
    assert v2 is not None
    assert v2.content == {"chapter": 1}


async def test_list_truth_files(db_session: AsyncSession):
    project = await _create_project(db_session)
    # Add another truth file
    tf2 = TruthFile(
        project_id=project.id, file_type="story_bible", content={}, version=1
    )
    db_session.add(tf2)
    await db_session.flush()

    mgr = StateManager(db_session)
    files = await mgr.list_truth_files(project.id)
    assert len(files) == 2
    types = {f.file_type for f in files}
    assert types == {"current_state", "story_bible"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_state_manager.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement State Manager**

```python
# backend/app/engines/state_manager.py
"""State Manager: truth file CRUD with atomic versioning and history."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.truth_file import TruthFile, TruthFileHistory


class StateManager:
    """Manages the 10 truth files with version control."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_truth_file(
        self, project_id: UUID, file_type: str
    ) -> TruthFile | None:
        stmt = select(TruthFile).where(
            TruthFile.project_id == project_id,
            TruthFile.file_type == file_type,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_truth_files(self, project_id: UUID) -> list[TruthFile]:
        stmt = select(TruthFile).where(TruthFile.project_id == project_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_truth_file(
        self,
        project_id: UUID,
        file_type: str,
        diff: dict,
        chapter_id: UUID | None = None,
    ) -> TruthFile:
        """Atomic update: save current version to history, apply diff, bump version."""
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            raise ValueError(
                f"Truth file '{file_type}' not found for project {project_id}"
            )

        # Save current state to history
        history = TruthFileHistory(
            truth_file_id=tf.id,
            version=tf.version,
            content=tf.content,
            changed_by_chapter_id=chapter_id,
        )
        self.db.add(history)

        # Apply diff (full replace for now; could do deep merge later)
        tf.content = diff
        tf.version += 1
        tf.updated_by_chapter_id = chapter_id
        await self.db.flush()
        return tf

    async def get_history(
        self, project_id: UUID, file_type: str
    ) -> list[TruthFileHistory]:
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            return []
        stmt = (
            select(TruthFileHistory)
            .where(TruthFileHistory.truth_file_id == tf.id)
            .order_by(TruthFileHistory.version)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_truth_file_at_version(
        self, project_id: UUID, file_type: str, version: int
    ) -> TruthFileHistory | None:
        tf = await self.get_truth_file(project_id, file_type)
        if tf is None:
            return None
        stmt = select(TruthFileHistory).where(
            TruthFileHistory.truth_file_id == tf.id,
            TruthFileHistory.version == version,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_state_manager.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/state_manager.py backend/tests/test_state_manager.py
git commit -m "feat(iter2): implement StateManager with version history"
```

---

### Task 5: World Model Engine (Entity Extraction + Matching)

**Files:**
- Create: `backend/app/engines/world_model.py`
- Create: `backend/tests/test_world_model.py`

Uses jieba for word segmentation and pyahocorasick for fast multi-pattern matching.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_world_model.py
import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.world_model import WorldModelEngine
from app.models.project import Project
from app.models.entity import Entity


async def _setup_project_with_entities(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    e1 = Entity(
        project_id=project.id,
        name="叶辰",
        aliases=["叶少", "辰哥"],
        entity_type="character",
        attributes={"level": "筑基"},
        confidence=1.0,
        source="manual",
    )
    e2 = Entity(
        project_id=project.id,
        name="青云宗",
        aliases=["青云"],
        entity_type="faction",
        attributes={},
        confidence=1.0,
        source="manual",
    )
    db.add_all([e1, e2])
    await db.flush()
    return project, e1, e2


async def test_build_automaton(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)

    automaton = await engine.build_automaton(project.id)

    # Automaton should contain all names and aliases
    assert "叶辰" in automaton
    assert "叶少" in automaton
    assert "辰哥" in automaton
    assert "青云宗" in automaton
    assert "青云" in automaton


async def test_match_entities(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)

    text = "叶辰来到青云宗大门前，叶少看着高耸的山门。"
    matches = await engine.match_entities(text, project.id)

    matched_names = {m["name"] for m in matches}
    assert "叶辰" in matched_names
    assert "青云宗" in matched_names


async def test_match_entities_with_aliases(db_session: AsyncSession):
    project, e1, e2 = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)

    text = "辰哥一步踏入青云修炼之地。"
    matches = await engine.match_entities(text, project.id)

    # "辰哥" is an alias of 叶辰, "青云" is an alias of 青云宗
    entity_ids = {m["entity_id"] for m in matches}
    assert e1.id in entity_ids
    assert e2.id in entity_ids


async def test_match_entities_empty_text(db_session: AsyncSession):
    project, _, _ = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)

    matches = await engine.match_entities("", project.id)
    assert matches == []


async def test_extract_new_entities_with_jieba(db_session: AsyncSession):
    project, _, _ = await _setup_project_with_entities(db_session)
    engine = WorldModelEngine(db_session)

    text = "苏灵儿站在天剑阁的门口，望着远处的万丈深渊。"
    # jieba NER extraction (basic: proper nouns)
    extracted = await engine.extract_entities_jieba(text)

    # Should return candidate entities (names/locations found by jieba)
    assert isinstance(extracted, list)
    # jieba may or may not find these depending on its dictionary
    # Just verify the interface works and returns a list of dicts
    for item in extracted:
        assert "text" in item
        assert "flag" in item
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_world_model.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement World Model Engine**

```python
# backend/app/engines/world_model.py
"""World Model Engine: entity matching (Aho-Corasick) + extraction (jieba)."""

from uuid import UUID

import ahocorasick
import jieba
import jieba.posseg as pseg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity


class WorldModelEngine:
    """Manages entity extraction and real-time text matching."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._automaton_cache: dict[UUID, ahocorasick.Automaton] = {}

    async def build_automaton(self, project_id: UUID) -> ahocorasick.Automaton:
        """Build an Aho-Corasick automaton from all entities in a project."""
        stmt = select(Entity).where(Entity.project_id == project_id)
        result = await self.db.execute(stmt)
        entities = list(result.scalars().all())

        automaton = ahocorasick.Automaton()

        for entity in entities:
            # Add main name
            automaton.add_word(entity.name, (str(entity.id), entity.name, entity.name))
            # Add aliases
            for alias in entity.aliases:
                if alias:
                    automaton.add_word(
                        alias, (str(entity.id), entity.name, alias)
                    )

        automaton.make_automaton()
        self._automaton_cache[project_id] = automaton
        return automaton

    async def match_entities(
        self, text: str, project_id: UUID
    ) -> list[dict]:
        """Match entities in text using Aho-Corasick automaton.

        Returns list of dicts: {"entity_id": UUID, "name": str, "matched_text": str, "position": int}
        """
        if not text:
            return []

        automaton = self._automaton_cache.get(project_id)
        if automaton is None:
            automaton = await self.build_automaton(project_id)

        if not automaton:
            return []

        seen: set[str] = set()
        matches: list[dict] = []

        for end_pos, (entity_id_str, name, matched_text) in automaton.iter(text):
            key = f"{entity_id_str}:{matched_text}"
            if key not in seen:
                seen.add(key)
                matches.append(
                    {
                        "entity_id": UUID(entity_id_str),
                        "name": name,
                        "matched_text": matched_text,
                        "position": end_pos - len(matched_text) + 1,
                    }
                )

        return matches

    async def extract_entities_jieba(self, text: str) -> list[dict]:
        """Extract candidate entities from text using jieba POS tagging.

        Returns candidate entities with POS flags. Proper nouns (nr, ns, nt, nz)
        are the most likely entity candidates.
        """
        if not text:
            return []

        # POS tags of interest: nr=person, ns=place, nt=org, nz=other proper noun
        interesting_flags = {"nr", "ns", "nt", "nz"}

        candidates: list[dict] = []
        seen: set[str] = set()

        for word, flag in pseg.cut(text):
            if flag in interesting_flags and word not in seen and len(word) >= 2:
                seen.add(word)
                candidates.append({"text": word, "flag": flag})

        return candidates

    def invalidate_cache(self, project_id: UUID) -> None:
        """Clear the automaton cache for a project (call after entity changes)."""
        self._automaton_cache.pop(project_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_world_model.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/world_model.py backend/tests/test_world_model.py
git commit -m "feat(iter2): implement WorldModelEngine with Aho-Corasick matching"
```

---

### Task 6: Context Filter Engine (POV-Aware)

**Files:**
- Create: `backend/app/engines/context_filter.py`
- Create: `backend/tests/test_context_filter.py`

Assembles context for the Writer agent, filtering by POV character's knowledge boundary.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_context_filter.py
import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.context_filter import ContextFilter
from app.models.project import Project
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.truth_file import TruthFile
from app.models.scene_card import SceneCard
from app.models.memory_entry import MemoryEntry


async def _setup_context_data(db: AsyncSession):
    """Create a project with volumes, chapters, entities, truth files, and scene cards."""
    project = Project(title="Test Novel", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    volume = Volume(project_id=project.id, title="Volume 1", sort_order=1)
    db.add(volume)
    await db.flush()

    # POV character
    pov = Entity(
        project_id=project.id,
        name="叶辰",
        entity_type="character",
        knowledge_boundary={"known_events": ["arrived_at_sect"]},
        confidence=1.0,
        source="manual",
    )
    # Non-POV character with secret
    secret_char = Entity(
        project_id=project.id,
        name="暗影",
        entity_type="character",
        knowledge_boundary={"secret": "is_the_spy"},
        confidence=1.0,
        source="manual",
    )
    db.add_all([pov, secret_char])
    await db.flush()

    # Previous chapter with summary
    ch1 = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter 1",
        sort_order=1,
        pov_character_id=pov.id,
        status="final",
        summary="叶辰来到青云宗。",
    )
    db.add(ch1)
    await db.flush()

    # Current chapter
    ch2 = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Chapter 2",
        sort_order=2,
        pov_character_id=pov.id,
        status="planned",
    )
    db.add(ch2)
    await db.flush()

    # Scene card for chapter 2
    sc = SceneCard(
        chapter_id=ch2.id,
        sort_order=1,
        pov_character_id=pov.id,
        location="青云宗大殿",
        goal="参加入门测试",
        conflict="测试中遇到强敌",
    )
    db.add(sc)

    # Truth files
    tf_state = TruthFile(
        project_id=project.id,
        file_type="current_state",
        content={"last_chapter": 1, "day": 2},
        version=1,
    )
    tf_bible = TruthFile(
        project_id=project.id,
        file_type="story_bible",
        content={"world": "修仙世界", "power_system": "灵力"},
        version=1,
    )
    db.add_all([tf_state, tf_bible])
    await db.flush()

    return project, volume, pov, ch1, ch2


async def test_assemble_context(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)

    ctx = await cf.assemble_context(ch2.id, pov.id)

    assert "system_prompt" in ctx
    assert "user_prompt" in ctx
    assert ctx["context_tokens"] > 0
    # Should include story bible and current state
    assert "修仙世界" in ctx["sections"]["story_bible"]
    # Should include previous chapter summary
    assert "叶辰来到青云宗" in ctx["sections"]["chapter_summaries"]
    # Should include scene card
    assert "参加入门测试" in ctx["sections"]["scene_cards"]


async def test_pov_filtering(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)

    ctx = await cf.assemble_context(ch2.id, pov.id)

    # POV character's knowledge boundary should be included
    sections_text = str(ctx["sections"])
    # Secret character's secret should NOT appear in POV context
    assert "is_the_spy" not in sections_text


async def test_assemble_context_no_pov(db_session: AsyncSession):
    project, volume, pov, ch1, ch2 = await _setup_context_data(db_session)
    cf = ContextFilter(db_session)

    # Without POV, should still work (no filtering)
    ctx = await cf.assemble_context(ch2.id, pov_character_id=None)
    assert ctx["context_tokens"] > 0


async def test_assemble_context_chapter_not_found(db_session: AsyncSession):
    cf = ContextFilter(db_session)
    with pytest.raises(ValueError, match="Chapter .* not found"):
        await cf.assemble_context(uuid4(), None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_context_filter.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement Context Filter**

```python
# backend/app/engines/context_filter.py
"""Context Filter: POV-aware context assembly for the Writer agent."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.scene_card import SceneCard
from app.models.truth_file import TruthFile


class ContextFilter:
    """Assembles context for Writer, filtered by POV character's knowledge boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble_context(
        self,
        chapter_id: UUID,
        pov_character_id: UUID | None = None,
    ) -> dict:
        """Assemble full context for writing a chapter.

        Returns dict with: system_prompt, user_prompt, context_tokens, sections.
        """
        # Load chapter
        chapter = await self._get_chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")

        project_id = chapter.project_id

        # Gather all context sections
        sections: dict[str, str] = {}

        # 1. Story bible
        story_bible = await self._get_truth_file_content(project_id, "story_bible")
        if story_bible:
            sections["story_bible"] = self._format_dict(story_bible)

        # 2. Current state
        current_state = await self._get_truth_file_content(project_id, "current_state")
        if current_state:
            sections["current_state"] = self._format_dict(current_state)

        # 3. Previous chapter summaries (POV-filtered if applicable)
        summaries = await self._get_chapter_summaries(
            project_id, chapter.sort_order, pov_character_id
        )
        if summaries:
            sections["chapter_summaries"] = summaries

        # 4. Scene cards for this chapter
        scene_cards = await self._get_scene_cards(chapter_id)
        if scene_cards:
            sections["scene_cards"] = scene_cards

        # 5. POV character state
        if pov_character_id:
            pov_state = await self._get_pov_state(pov_character_id)
            if pov_state:
                sections["pov_character"] = pov_state

        # Build prompts
        system_prompt = self._build_system_prompt(sections)
        user_prompt = self._build_user_prompt(chapter, sections)

        # Estimate tokens (rough: 1 Chinese char ≈ 1.5 tokens)
        all_text = system_prompt + user_prompt
        context_tokens = int(len(all_text) * 1.5)

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "context_tokens": context_tokens,
            "sections": sections,
        }

    async def _get_chapter(self, chapter_id: UUID) -> Chapter | None:
        stmt = select(Chapter).where(Chapter.id == chapter_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_truth_file_content(
        self, project_id: UUID, file_type: str
    ) -> dict | None:
        stmt = select(TruthFile).where(
            TruthFile.project_id == project_id,
            TruthFile.file_type == file_type,
        )
        result = await self.db.execute(stmt)
        tf = result.scalar_one_or_none()
        return tf.content if tf and tf.content else None

    async def _get_chapter_summaries(
        self,
        project_id: UUID,
        current_sort_order: int,
        pov_character_id: UUID | None,
    ) -> str:
        """Get summaries of previous chapters, filtered by POV if applicable."""
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.sort_order < current_sort_order,
                Chapter.summary.isnot(None),
            )
            .order_by(Chapter.sort_order)
        )
        result = await self.db.execute(stmt)
        chapters = list(result.scalars().all())

        if not chapters:
            return ""

        # If POV filtering, only include chapters where POV character was present
        if pov_character_id:
            chapters = [
                ch
                for ch in chapters
                if ch.pov_character_id == pov_character_id
                or ch.pov_character_id is None
            ]

        lines = []
        for ch in chapters[-5:]:  # Last 5 chapters max
            lines.append(f"[{ch.title}] {ch.summary}")
        return "\n".join(lines)

    async def _get_scene_cards(self, chapter_id: UUID) -> str:
        stmt = (
            select(SceneCard)
            .where(SceneCard.chapter_id == chapter_id)
            .order_by(SceneCard.sort_order)
        )
        result = await self.db.execute(stmt)
        cards = list(result.scalars().all())

        if not cards:
            return ""

        lines = []
        for card in cards:
            parts = [f"Scene {card.sort_order}"]
            if card.location:
                parts.append(f"Location: {card.location}")
            parts.append(f"Goal: {card.goal}")
            if card.conflict:
                parts.append(f"Conflict: {card.conflict}")
            if card.outcome:
                parts.append(f"Outcome: {card.outcome}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    async def _get_pov_state(self, pov_character_id: UUID) -> str:
        stmt = select(Entity).where(Entity.id == pov_character_id)
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if not entity:
            return ""

        parts = [f"POV: {entity.name} ({entity.entity_type})"]
        if entity.attributes:
            parts.append(f"Attributes: {self._format_dict(entity.attributes)}")
        if entity.knowledge_boundary:
            parts.append(
                f"Knowledge: {self._format_dict(entity.knowledge_boundary)}"
            )
        return "\n".join(parts)

    def _build_system_prompt(self, sections: dict[str, str]) -> str:
        parts = ["You are a novel writer."]
        if "story_bible" in sections:
            parts.append(f"\n## World Setting\n{sections['story_bible']}")
        return "\n".join(parts)

    def _build_user_prompt(self, chapter: Chapter, sections: dict[str, str]) -> str:
        parts = [f"## Chapter: {chapter.title}"]
        if "current_state" in sections:
            parts.append(f"\n## Current State\n{sections['current_state']}")
        if "chapter_summaries" in sections:
            parts.append(f"\n## Previous Chapters\n{sections['chapter_summaries']}")
        if "scene_cards" in sections:
            parts.append(f"\n## Scene Cards\n{sections['scene_cards']}")
        if "pov_character" in sections:
            parts.append(f"\n## POV Character\n{sections['pov_character']}")
        parts.append("\nPlease write this chapter.")
        return "\n".join(parts)

    @staticmethod
    def _format_dict(d: dict) -> str:
        return ", ".join(f"{k}: {v}" for k, v in d.items())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_context_filter.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/context_filter.py backend/tests/test_context_filter.py
git commit -m "feat(iter2): implement ContextFilter with POV-aware assembly"
```

---

### Task 7: Celery App + Docker Compose Update

**Files:**
- Create: `backend/app/jobs/celery_app.py`
- Create: `backend/tests/test_celery_config.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_celery_config.py
from app.jobs.celery_app import celery_app


def test_celery_app_exists():
    assert celery_app is not None
    assert celery_app.main == "aiwriter"


def test_celery_queues_configured():
    queues = celery_app.conf.task_queues
    queue_names = {q.name for q in queues}
    assert "default" in queue_names
    assert "writing" in queue_names
    assert "audit" in queue_names


def test_celery_default_queue():
    assert celery_app.conf.task_default_queue == "default"


def test_celery_serializer():
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_celery_config.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement Celery app**

```python
# backend/app/jobs/celery_app.py
"""Celery application configuration with 3 queues."""

from celery import Celery
from kombu import Queue

from app.config import settings

celery_app = Celery(
    "aiwriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Queues
    task_queues=(
        Queue("default"),
        Queue("writing"),
        Queue("audit"),
    ),
    task_default_queue="default",
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timeouts
    task_soft_time_limit=300,  # 5 min soft
    task_time_limit=600,  # 10 min hard
    # Worker
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    # Results
    result_expires=3600,  # 1 hour
    # Misc
    task_track_started=True,
    task_acks_late=True,
    timezone="UTC",
)

# Auto-discover tasks in app.jobs
celery_app.autodiscover_tasks(["app.jobs"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_celery_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Update docker-compose.yml**

Add `celery-worker` and `celery-beat` services after the `backend` service in `docker-compose.yml`:

```yaml
  celery-worker:
    build: ./backend
    command: celery -A app.jobs.celery_app worker -l info -c 4 -Q default,writing,audit
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+asyncpg://aiwriter:${DB_PASSWORD:-aiwriter_dev}@postgres/aiwriter
      REDIS_URL: redis://redis:6379
      AUTH_TOKEN: ${AUTH_TOKEN:-dev-token-change-me}

  celery-beat:
    build: ./backend
    command: celery -A app.jobs.celery_app beat -l info
    depends_on:
      redis: { condition: service_healthy }
    environment:
      REDIS_URL: redis://redis:6379
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/jobs/celery_app.py backend/tests/test_celery_config.py docker-compose.yml
git commit -m "feat(iter2): configure Celery with 3 queues + Docker services"
```

---

### Task 8: RadarAgent

**Files:**
- Create: `backend/app/agents/radar.py`
- Create: `backend/tests/test_agent_radar.py`

Radar analyzes project state and determines the next action.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_radar.py
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.radar import RadarAgent
from app.providers.base import BaseLLMProvider, ChatMessage, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response_content: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(
            content=response_content, model="gpt-4o", usage={"input_tokens": 50, "output_tokens": 20}
        )
    )
    return provider


async def test_radar_execute_success():
    response = json.dumps({
        "next_action": "write_chapter",
        "target_chapter_id": str(uuid4()),
        "reasoning": "Chapter 1 is planned and ready to write.",
    })
    provider = _mock_provider(response)
    agent = RadarAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.agent_name == "radar"
    assert result.data["next_action"] == "write_chapter"


async def test_radar_execute_done():
    response = json.dumps({
        "next_action": "done",
        "reasoning": "All chapters are finalized.",
    })
    provider = _mock_provider(response)
    agent = RadarAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["next_action"] == "done"


async def test_radar_build_messages():
    provider = _mock_provider("{}")
    agent = RadarAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        pipeline_data={"project_status": "has 3 planned chapters"},
    )

    messages = await agent.build_messages(ctx)

    assert len(messages) >= 2
    assert messages[0].role == "system"
    assert "radar" in messages[0].content.lower() or "analyze" in messages[0].content.lower()
    assert messages[-1].role == "user"


async def test_radar_handles_invalid_json():
    provider = _mock_provider("not valid json at all")
    agent = RadarAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4())

    result = await agent.execute(ctx)

    # Should fail gracefully
    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_radar.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement RadarAgent**

```python
# backend/app/agents/radar.py
"""Radar Agent: analyzes project state and determines next pipeline action."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, RadarOutput, ValidationIssue


class RadarAgent(BaseAgent):
    name = "radar"
    description = "Analyzes project state and determines the next action"
    temperature = 0.3

    SYSTEM_PROMPT = """You are a project analysis agent for a novel writing system.
Your job is to analyze the current state of a writing project and determine what action should be taken next.

You must respond with valid JSON matching this schema:
{
    "next_action": "write_chapter" | "plan_volume" | "plan_chapters" | "done",
    "target_chapter_id": "<uuid or null>",
    "target_volume_id": "<uuid or null>",
    "reasoning": "<brief explanation>"
}

Rules:
- If there are planned chapters ready to write, return "write_chapter" with the chapter ID.
- If a volume needs chapter planning, return "plan_chapters" with the volume ID.
- If the project needs a new volume outline, return "plan_volume".
- If all chapters are finalized, return "done".
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        user_content = "Analyze the current project state and determine the next action.\n\n"
        if context.pipeline_data:
            user_content += f"Project data:\n{json.dumps(context.pipeline_data, ensure_ascii=False, default=str)}"
        else:
            user_content += f"Project ID: {context.project_id}"

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        parsed = json.loads(resp.content)
        return RadarOutput(**parsed).model_dump()

    async def validate_output(self, result: Any) -> list[ValidationIssue]:
        issues = []
        if isinstance(result, dict):
            action = result.get("next_action", "")
            valid_actions = {"write_chapter", "plan_volume", "plan_chapters", "done"}
            if action not in valid_actions:
                issues.append(
                    ValidationIssue(
                        field="next_action",
                        message=f"Invalid action: {action}",
                        severity="error",
                    )
                )
        return issues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_radar.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/radar.py backend/tests/test_agent_radar.py
git commit -m "feat(iter2): implement RadarAgent"
```

---

### Task 9: ArchitectAgent

**Files:**
- Create: `backend/app/agents/architect.py`
- Create: `backend/tests/test_agent_architect.py`

Architect handles structure planning: plot blueprint, volume outline, chapter plan, scene cards.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_architect.py
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.architect import ArchitectAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response_content: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(content=response_content, model="gpt-4o", usage={})
    )
    return provider


async def test_architect_chapter_plan():
    response = json.dumps({
        "stage": "chapter_plan",
        "content": {
            "chapters": [
                {"title": "Chapter 1", "summary": "Hero arrives", "sort_order": 1},
                {"title": "Chapter 2", "summary": "First trial", "sort_order": 2},
            ]
        },
    })
    provider = _mock_provider(response)
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        volume_id=uuid4(),
        params={"stage": "chapter_plan"},
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["stage"] == "chapter_plan"
    assert len(result.data["content"]["chapters"]) == 2


async def test_architect_scene_cards():
    response = json.dumps({
        "stage": "scene_cards",
        "content": {
            "scenes": [
                {
                    "sort_order": 1,
                    "location": "Mountain gate",
                    "goal": "Enter the sect",
                    "conflict": "Guardian blocks entry",
                },
            ]
        },
    })
    provider = _mock_provider(response)
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        params={"stage": "scene_cards"},
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["stage"] == "scene_cards"


async def test_architect_build_messages():
    provider = _mock_provider("{}")
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        params={"stage": "volume_outline"},
        pipeline_data={"genre": "xuanhuan"},
    )

    messages = await agent.build_messages(ctx)

    assert len(messages) >= 2
    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    # Should mention the stage
    user_msg = messages[-1].content
    assert "volume_outline" in user_msg


async def test_architect_invalid_json():
    provider = _mock_provider("not json")
    agent = ArchitectAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4(), params={"stage": "chapter_plan"})

    result = await agent.execute(ctx)

    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_architect.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement ArchitectAgent**

```python
# backend/app/agents/architect.py
"""Architect Agent: structure planning (plot blueprint, volume outline, chapters, scene cards)."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ArchitectOutput


class ArchitectAgent(BaseAgent):
    name = "architect"
    description = "Plans story structure: outlines, chapters, and scene cards"
    temperature = 0.4

    SYSTEM_PROMPT = """You are a story architect for a novel writing system.
Your job is to create structured outlines and plans for novels.

You must respond with valid JSON matching this schema:
{
    "stage": "<the planning stage>",
    "content": { <structured content varies by stage> }
}

Planning stages:
- "plot_blueprint": Overall story arc with major turning points
- "volume_outline": Volume-level structure with objectives and climax hints
- "chapter_plan": List of chapters with titles, summaries, and sort orders
- "scene_cards": Detailed scene breakdowns with location, goal, conflict, outcome

Guidelines:
- Each chapter should have clear goals and conflicts
- Scene cards must include at least: location, goal, and conflict
- Follow the genre conventions provided in context
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        stage = context.params.get("stage", "chapter_plan")
        user_content = f"Planning stage: {stage}\n\n"

        if context.pipeline_data:
            user_content += f"Context:\n{json.dumps(context.pipeline_data, ensure_ascii=False, default=str)}\n\n"

        if context.volume_id:
            user_content += f"Volume ID: {context.volume_id}\n"
        if context.chapter_id:
            user_content += f"Chapter ID: {context.chapter_id}\n"

        user_content += f"\nPlease create the {stage} structure."

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        parsed = json.loads(resp.content)
        return ArchitectOutput(**parsed).model_dump()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_architect.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/architect.py backend/tests/test_agent_architect.py
git commit -m "feat(iter2): implement ArchitectAgent"
```

---

### Task 10: ContextAgent (Non-LLM)

**Files:**
- Create: `backend/app/agents/context_agent.py`
- Create: `backend/tests/test_agent_context.py`

ContextAgent is a **non-LLM** agent: it gathers and assembles context from the DB using ContextFilter.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_context.py
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context_agent import ContextAgent
from app.models.chapter import Chapter
from app.models.entity import Entity
from app.models.project import Project
from app.models.scene_card import SceneCard
from app.models.truth_file import TruthFile
from app.models.volume import Volume
from app.schemas.agent import AgentContext


async def _setup_data(db: AsyncSession):
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()

    volume = Volume(project_id=project.id, title="V1", sort_order=1)
    db.add(volume)
    await db.flush()

    pov = Entity(
        project_id=project.id,
        name="Hero",
        entity_type="character",
        confidence=1.0,
        source="manual",
    )
    db.add(pov)
    await db.flush()

    ch = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Ch1",
        sort_order=1,
        pov_character_id=pov.id,
        status="planned",
    )
    db.add(ch)
    await db.flush()

    sc = SceneCard(
        chapter_id=ch.id, sort_order=1, goal="Test goal", conflict="Test conflict"
    )
    tf = TruthFile(
        project_id=project.id,
        file_type="story_bible",
        content={"setting": "fantasy"},
        version=1,
    )
    db.add_all([sc, tf])
    await db.flush()
    return project, ch, pov


async def test_context_agent_execute(db_session: AsyncSession):
    project, ch, pov = await _setup_data(db_session)
    agent = ContextAgent().set_db(db_session)

    ctx = AgentContext(
        project_id=project.id,
        chapter_id=ch.id,
        params={"pov_character_id": str(pov.id)},
    )
    result = await agent.execute(ctx)

    assert result.success is True
    assert result.agent_name == "context"
    assert "system_prompt" in result.data
    assert "user_prompt" in result.data
    assert result.data["context_tokens"] > 0


async def test_context_agent_no_chapter(db_session: AsyncSession):
    agent = ContextAgent().set_db(db_session)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is False
    assert "not found" in result.error.lower()


async def test_context_agent_without_pov(db_session: AsyncSession):
    project, ch, _ = await _setup_data(db_session)
    agent = ContextAgent().set_db(db_session)
    ctx = AgentContext(project_id=project.id, chapter_id=ch.id)

    result = await agent.execute(ctx)

    assert result.success is True


async def test_context_agent_no_db():
    """ContextAgent should fail if db session not set."""
    agent = ContextAgent()
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is False
    assert "db session" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_context.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement ContextAgent**

```python
# backend/app/agents/context_agent.py
"""Context Agent: non-LLM agent that assembles writing context from the database."""

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.context_filter import ContextFilter
from app.providers.base import BaseLLMProvider, ChatMessage
from app.schemas.agent import AgentContext, AgentResult


class ContextAgent:
    """Non-LLM agent: gathers context for the Writer using ContextFilter.

    Unlike other agents, this does not extend BaseAgent because it makes no LLM calls.
    It accepts provider/model args for API compatibility with the agent registry,
    but ignores them. Requires a db session to be set via set_db() before execution.
    """

    name = "context"
    description = "Assembles writing context from DB (no LLM)"

    def __init__(self, provider: BaseLLMProvider | None = None, model: str = ""):
        # provider/model accepted for registry compatibility but unused
        self._db: AsyncSession | None = None

    def set_db(self, db: AsyncSession) -> "ContextAgent":
        """Set the database session. Must be called before execute()."""
        self._db = db
        return self

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()
        try:
            if self._db is None:
                raise RuntimeError("ContextAgent requires db session (call set_db())")
            if context.chapter_id is None:
                raise ValueError("chapter_id is required for ContextAgent")

            pov_id_str = context.params.get("pov_character_id")
            pov_id = UUID(pov_id_str) if pov_id_str else None

            cf = ContextFilter(self._db)
            assembled = await cf.assemble_context(context.chapter_id, pov_id)

            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=assembled,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=elapsed,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_context.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/context_agent.py backend/tests/test_agent_context.py
git commit -m "feat(iter2): implement ContextAgent (non-LLM context assembly)"
```

---

### Task 11: WriterAgent (Phase1 + Phase2)

**Files:**
- Create: `backend/app/agents/writer.py`
- Create: `backend/tests/test_agent_writer.py`

Writer has two phases: Phase1 (creative writing) and Phase2 (state settlement extraction).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_writer.py
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.writer import WriterAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(*responses: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    side_effects = [
        ChatResponse(content=r, model="claude-sonnet", usage={}) for r in responses
    ]
    provider.chat = AsyncMock(side_effect=side_effects)
    return provider


async def test_writer_execute_success():
    creative_text = "叶辰踏入了青云宗的大门，眼前的景象让他震撼不已。高耸的山峰直插云霄。"
    settlement = json.dumps({
        "new_entities": [{"name": "青云宗", "type": "faction"}],
        "state_changes": {"location": "青云宗"},
        "summary": "叶辰进入青云宗",
    })
    provider = _mock_provider(creative_text, settlement)
    agent = WriterAgent(provider=provider)

    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        params={"target_words": 50},
        pipeline_data={
            "context": {
                "system_prompt": "You are a writer.",
                "user_prompt": "Write chapter 1.",
            }
        },
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["phase1_content"] == creative_text
    assert result.data["word_count"] > 0


async def test_writer_phase1_only():
    """Test that phase1 content is always present."""
    provider = _mock_provider("Some story text.", '{"summary": "test"}')
    agent = WriterAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is True
    assert "phase1_content" in result.data
    assert result.data["phase1_content"] == "Some story text."


async def test_writer_build_messages_with_context():
    provider = _mock_provider("text", "{}")
    agent = WriterAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={
            "context": {
                "system_prompt": "Custom system prompt.",
                "user_prompt": "Custom user prompt.",
            }
        },
    )

    messages = await agent.build_messages(ctx)

    assert messages[0].role == "system"
    assert "Custom system prompt" in messages[0].content
    assert messages[-1].role == "user"
    assert "Custom user prompt" in messages[-1].content


async def test_writer_handles_llm_failure():
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(side_effect=Exception("LLM timeout"))
    agent = WriterAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    result = await agent.execute(ctx)

    assert result.success is False
    assert "timeout" in result.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_writer.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement WriterAgent**

```python
# backend/app/agents/writer.py
"""Writer Agent: Phase1 (creative writing) + Phase2 (state settlement extraction)."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, WriterOutput


class WriterAgent(BaseAgent):
    name = "writer"
    description = "Writes novel chapters (Phase1: creative, Phase2: settlement)"
    temperature = 0.7
    output_schema = WriterOutput

    DEFAULT_SYSTEM = """You are a professional novel writer. Write vivid, engaging prose.

Rules:
- Show, don't tell
- Each scene must advance at least one conflict
- Dialogue must reflect character personality
- Include at least two sensory details per scene
- Write directly in prose, no metadata or annotations
"""

    SETTLEMENT_SYSTEM = """You are a fact extractor. Given a chapter text, extract:
1. New entities (characters, locations, items) mentioned
2. State changes (location changes, relationship changes, power level changes)
3. A brief summary of the chapter (1-2 sentences)

Respond in valid JSON:
{
    "new_entities": [{"name": "...", "type": "character|location|item|..."}],
    "state_changes": {"key": "value"},
    "summary": "..."
}
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        """Build Phase1 messages."""
        ctx_data = context.pipeline_data.get("context", {})
        system = ctx_data.get("system_prompt", self.DEFAULT_SYSTEM)
        user = ctx_data.get("user_prompt", "Please write this chapter.")

        target_words = context.params.get("target_words", 3000)
        user += f"\n\nTarget word count: {target_words} characters."

        return [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        """Execute both phases: Phase1 (creative) → Phase2 (settlement)."""
        # Phase 1: Creative writing
        resp1 = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=0.7,
        )
        phase1_content = resp1.content

        # Phase 2: State settlement extraction
        phase2_messages = [
            ChatMessage(role="system", content=self.SETTLEMENT_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Extract facts from this chapter:\n\n{phase1_content}",
            ),
        ]
        resp2 = await self.provider.chat(
            messages=phase2_messages,
            model=self.model,
            temperature=0.3,
        )
        try:
            phase2_data = json.loads(resp2.content)
        except json.JSONDecodeError:
            phase2_data = {"summary": resp2.content}

        return {
            "phase1_content": phase1_content,
            "phase2_settlement": phase2_data,
            "word_count": len(phase1_content),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_writer.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/writer.py backend/tests/test_agent_writer.py
git commit -m "feat(iter2): implement WriterAgent with Phase1 + Phase2"
```

---

### Task 12: SettlerAgent

**Files:**
- Create: `backend/app/agents/settler.py`
- Create: `backend/tests/test_agent_settler.py`

Settler extracts facts from written content and updates truth files.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_settler.py
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.settler import SettlerAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(content=response, model="gemini-flash", usage={})
    )
    return provider


async def test_settler_execute():
    response = json.dumps({
        "extracted_entities": [
            {"name": "叶辰", "type": "character", "confidence": 0.95},
            {"name": "青云宗", "type": "faction", "confidence": 0.9},
        ],
        "truth_file_updates": {
            "current_state": {"last_chapter": 1, "location": "青云宗"},
            "chapter_summaries": {"1": "叶辰加入青云宗"},
        },
    })
    provider = _mock_provider(response)
    agent = SettlerAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={
            "content": "叶辰来到青云宗...",
            "settlement": {"summary": "叶辰加入青云宗"},
        },
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert len(result.data["extracted_entities"]) == 2
    assert "current_state" in result.data["truth_file_updates"]


async def test_settler_build_messages():
    provider = _mock_provider("{}")
    agent = SettlerAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={
            "content": "Story text here.",
            "settlement": {"summary": "Things happened"},
        },
    )

    messages = await agent.build_messages(ctx)

    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    assert "Story text here" in messages[-1].content


async def test_settler_invalid_response():
    provider = _mock_provider("not json")
    agent = SettlerAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={"content": "text"},
    )

    result = await agent.execute(ctx)

    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_settler.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement SettlerAgent**

```python
# backend/app/agents/settler.py
"""Settler Agent: extracts facts and updates truth files after writing."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, SettlerOutput


class SettlerAgent(BaseAgent):
    name = "settler"
    description = "Extracts facts from written content and updates truth files"
    temperature = 0.2

    SYSTEM_PROMPT = """You are a fact extraction agent for a novel writing system.
Given a chapter's text and initial settlement data, you must:

1. Extract all entities mentioned (characters, locations, factions, items, concepts)
2. Determine what truth file updates are needed
3. Compute diffs for each truth file

Respond in valid JSON:
{
    "extracted_entities": [
        {"name": "...", "type": "character|location|faction|item|concept", "confidence": 0.0-1.0}
    ],
    "truth_file_updates": {
        "current_state": { ... },
        "chapter_summaries": { ... },
        "particle_ledger": { ... },
        "pending_hooks": { ... },
        "character_matrix": { ... }
    }
}

Only include truth file keys that actually need updates.
Entity confidence: >0.8 = auto-register, 0.5-0.8 = needs review, <0.5 = skip.
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        settlement = context.pipeline_data.get("settlement", {})

        user_msg = f"Chapter content:\n{content}\n\n"
        if settlement:
            user_msg += f"Writer settlement data:\n{json.dumps(settlement, ensure_ascii=False, default=str)}\n\n"
        user_msg += "Extract all facts and compute truth file diffs."

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_msg),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        parsed = json.loads(resp.content)
        return SettlerOutput(**parsed).model_dump()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_settler.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/settler.py backend/tests/test_agent_settler.py
git commit -m "feat(iter2): implement SettlerAgent"
```

---

### Task 13: AuditorAgent + ReviserAgent (Basic Framework)

**Files:**
- Create: `backend/app/agents/auditor.py`
- Create: `backend/app/agents/reviser.py`
- Create: `backend/tests/test_agent_auditor_reviser.py`

Basic framework versions. Full 33-dim audit and 5-mode revision come in iteration 3.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_auditor_reviser.py
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.auditor import AuditorAgent
from app.agents.reviser import ReviserAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(content=response, model="gpt-4o", usage={})
    )
    return provider


# --- Auditor tests ---

async def test_auditor_execute_pass():
    response = json.dumps({
        "scores": {"consistency": 8.5, "narrative": 7.0, "style": 9.0},
        "pass_rate": 1.0,
        "has_blocking": False,
        "issues": [],
        "recommendation": "pass",
    })
    provider = _mock_provider(response)
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={"draft_id": str(uuid4()), "content": "Good chapter text."},
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["recommendation"] == "pass"
    assert result.data["has_blocking"] is False


async def test_auditor_execute_needs_revision():
    response = json.dumps({
        "scores": {"consistency": 3.0, "narrative": 5.0},
        "pass_rate": 0.4,
        "has_blocking": True,
        "issues": [{"dimension": "consistency", "message": "Character OOC", "severity": "blocking"}],
        "recommendation": "revise",
    })
    provider = _mock_provider(response)
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={"draft_id": str(uuid4()), "content": "Bad text."},
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["recommendation"] == "revise"
    assert result.data["has_blocking"] is True


async def test_auditor_build_messages():
    provider = _mock_provider("{}")
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={"content": "Text to audit.", "mode": "full"},
    )

    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert "audit" in messages[0].content.lower()


# --- Reviser tests ---

async def test_reviser_execute():
    response = "叶辰踏入了青云宗的大门。这里的一切都与他想象中不同。"
    provider = _mock_provider(response)
    agent = ReviserAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={
            "content": "Original text.",
            "mode": "polish",
            "audit_issues": [{"dimension": "style", "message": "AI traces"}],
        },
    )

    result = await agent.execute(ctx)

    assert result.success is True
    assert result.data["revised_content"] != ""
    assert result.data["word_count"] > 0


async def test_reviser_build_messages():
    provider = _mock_provider("revised")
    agent = ReviserAgent(provider=provider)
    ctx = AgentContext(
        project_id=uuid4(),
        chapter_id=uuid4(),
        pipeline_data={
            "content": "Original.",
            "mode": "spot-fix",
            "audit_issues": [{"message": "fix this"}],
        },
    )

    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    assert "Original." in messages[-1].content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_auditor_reviser.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement AuditorAgent**

```python
# backend/app/agents/auditor.py
"""Auditor Agent: basic quality audit framework (full 33-dim in iteration 3)."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, AuditorOutput


class AuditorAgent(BaseAgent):
    name = "auditor"
    description = "Audits chapter quality across multiple dimensions"
    temperature = 0.2

    SYSTEM_PROMPT = """You are a quality auditor for a novel writing system.
Evaluate the given chapter text across these dimensions:
- consistency: Character behavior, world rules, timeline
- narrative: Plot advancement, scene goals, tension
- character: Dialogue consistency, character development
- structure: Three-act structure, pacing within chapter
- style: Writing quality, repetition, AI traces

For each dimension, give a score from 0-10.
Severity: pass (≥7), warning (4-6), error (1-3), blocking (0).

Respond in valid JSON:
{
    "scores": {"dimension_name": score, ...},
    "pass_rate": 0.0-1.0,
    "has_blocking": true/false,
    "issues": [{"dimension": "...", "message": "...", "severity": "pass|warning|error|blocking"}],
    "recommendation": "pass" | "revise" | "rework"
}

Rules:
- pass_rate = (dimensions with score ≥ 7) / total dimensions
- has_blocking = any score == 0
- recommendation: "pass" if pass_rate ≥ 0.85, "revise" if < 0.85, "rework" if < 0.6
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        mode = context.pipeline_data.get("mode", "full")

        user_msg = f"Audit mode: {mode}\n\nChapter content:\n{content}"

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_msg),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        parsed = json.loads(resp.content)
        return AuditorOutput(**parsed).model_dump()
```

- [ ] **Step 4: Implement ReviserAgent**

```python
# backend/app/agents/reviser.py
"""Reviser Agent: basic revision framework (full 5-mode in iteration 3)."""

from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import ChatMessage
from app.schemas.agent import AgentContext, ReviserOutput

import json


class ReviserAgent(BaseAgent):
    name = "reviser"
    description = "Revises chapter content based on audit feedback"
    temperature = 0.5
    output_schema = ReviserOutput

    MODE_PROMPTS = {
        "polish": "Lightly polish the text: fix grammar, improve flow, remove repetition.",
        "rewrite": "Rewrite problematic sections while maintaining plot continuity.",
        "rework": "Significantly rework the chapter to address major structural issues.",
        "spot-fix": "Fix only the specific issues listed below.",
        "anti-detect": "Rewrite to remove AI-like patterns while preserving meaning and style.",
    }

    SYSTEM_PROMPT = """You are a professional novel editor.
Your job is to revise chapter content based on audit feedback.

Output ONLY the revised chapter text. No explanations, no metadata, no annotations.
Maintain character voices, plot continuity, and the original style.
"""

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        content = context.pipeline_data.get("content", "")
        mode = context.pipeline_data.get("mode", "polish")
        issues = context.pipeline_data.get("audit_issues", [])

        mode_instruction = self.MODE_PROMPTS.get(mode, self.MODE_PROMPTS["polish"])

        user_parts = [
            f"Revision mode: {mode}",
            f"Instruction: {mode_instruction}",
        ]

        if issues:
            user_parts.append(
                f"Issues to fix:\n{json.dumps(issues, ensure_ascii=False, default=str)}"
            )

        user_parts.append(f"\nOriginal text:\n{content}")

        return [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content="\n\n".join(user_parts)),
        ]

    async def _call_llm(
        self, messages: list[ChatMessage], context: AgentContext
    ) -> Any:
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        mode = context.pipeline_data.get("mode", "polish")
        return {
            "revised_content": resp.content,
            "changes_summary": f"Revised in {mode} mode",
            "word_count": len(resp.content),
        }
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_agent_auditor_reviser.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/auditor.py backend/app/agents/reviser.py backend/tests/test_agent_auditor_reviser.py
git commit -m "feat(iter2): implement AuditorAgent + ReviserAgent (basic framework)"
```

---

### Task 14: Pipeline DAG Executor

**Files:**
- Create: `backend/app/orchestration/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

DAG executor with topological sort, conditional branching, and loop support.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pipeline.py
import pytest
from uuid import uuid4

from app.orchestration.pipeline import (
    PipelineDAG,
    PipelineNode,
    PipelineEdge,
    PipelineExecutor,
)
from app.schemas.agent import AgentResult


# --- DAG construction tests ---

def test_create_pipeline():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="architect", agent_name="architect"))
    dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))

    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1


def test_topological_sort():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="radar"))
    dag.add_node(PipelineNode(name="b", agent_name="architect"))
    dag.add_node(PipelineNode(name="c", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="c"))

    order = dag.topological_sort()
    assert order == ["a", "b", "c"]


def test_topological_sort_parallel():
    """Nodes at the same level can be in any order."""
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="start", agent_name="radar"))
    dag.add_node(PipelineNode(name="branch_a", agent_name="context"))
    dag.add_node(PipelineNode(name="branch_b", agent_name="context"))
    dag.add_node(PipelineNode(name="end", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="start", to_node="branch_a"))
    dag.add_edge(PipelineEdge(from_node="start", to_node="branch_b"))
    dag.add_edge(PipelineEdge(from_node="branch_a", to_node="end"))
    dag.add_edge(PipelineEdge(from_node="branch_b", to_node="end"))

    order = dag.topological_sort()
    assert order[0] == "start"
    assert order[-1] == "end"
    assert set(order[1:3]) == {"branch_a", "branch_b"}


def test_topological_sort_cycle_detection():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="radar"))
    dag.add_node(PipelineNode(name="b", agent_name="architect"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="a"))

    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort()


def test_loop_back_edge_excluded_from_topo_sort():
    """Loop-back edges should not cause cycle detection to fail."""
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_edge(PipelineEdge(from_node="auditor", to_node="reviser"))
    dag.add_edge(PipelineEdge(from_node="reviser", to_node="auditor", is_loop_back=True))

    # Should NOT raise - loop-back edges are excluded
    order = dag.topological_sort()
    assert "auditor" in order
    assert "reviser" in order


def test_conditional_edge():
    edge = PipelineEdge(
        from_node="auditor",
        to_node="reviser",
        condition=lambda result: result.get("recommendation") == "revise",
    )
    assert edge.condition({"recommendation": "revise"}) is True
    assert edge.condition({"recommendation": "pass"}) is False


def test_get_next_nodes():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="radar"))
    dag.add_edge(PipelineEdge(
        from_node="auditor",
        to_node="reviser",
        condition=lambda r: r.get("recommendation") == "revise",
    ))
    dag.add_edge(PipelineEdge(
        from_node="auditor",
        to_node="done",
        condition=lambda r: r.get("recommendation") == "pass",
    ))

    # Simulate auditor returning "revise"
    next_nodes = dag.get_next_nodes("auditor", {"recommendation": "revise"})
    assert next_nodes == ["reviser"]

    next_nodes = dag.get_next_nodes("auditor", {"recommendation": "pass"})
    assert next_nodes == ["finalize"]


# --- Standard chapter DAG ---

def test_build_chapter_dag():
    dag = PipelineDAG.build_chapter_dag()

    order = dag.topological_sort()
    # Should start with radar and contain all agents
    assert order[0] == "radar"
    assert "writer" in order
    assert "settler" in order
    assert "auditor" in order
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement Pipeline DAG**

```python
# backend/app/orchestration/pipeline.py
"""Pipeline DAG executor: topological sort, conditional branching, loop support."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PipelineNode:
    """A node in the pipeline DAG, representing an agent execution."""
    name: str
    agent_name: str
    params: dict[str, Any] = field(default_factory=dict)
    max_loops: int = 1  # >1 enables looping (e.g., Auditor↔Reviser)


@dataclass
class PipelineEdge:
    """A directed edge in the DAG, optionally with a condition."""
    from_node: str
    to_node: str
    condition: Callable[[dict], bool] | None = None
    is_loop_back: bool = False  # Loop-back edges are excluded from topological sort


class PipelineDAG:
    """Directed Acyclic Graph for agent pipeline execution."""

    def __init__(self):
        self.nodes: dict[str, PipelineNode] = {}
        self.edges: list[PipelineEdge] = []
        self._adjacency: dict[str, list[PipelineEdge]] = defaultdict(list)

    def add_node(self, node: PipelineNode) -> None:
        self.nodes[node.name] = node

    def add_edge(self, edge: PipelineEdge) -> None:
        self.edges.append(edge)
        self._adjacency[edge.from_node].append(edge)

    def topological_sort(self) -> list[str]:
        """Return nodes in topological order. Ignores loop-back edges. Raises ValueError on cycle."""
        # Only consider forward edges for topological sort
        forward_edges = [e for e in self.edges if not e.is_loop_back]

        in_degree: dict[str, int] = {name: 0 for name in self.nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in forward_edges:
            if edge.to_node in in_degree:
                in_degree[edge.to_node] += 1
                adj[edge.from_node].append(edge.to_node)

        queue = deque(
            name for name, deg in in_degree.items() if deg == 0
        )
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for next_node in adj.get(node, []):
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)

        if len(result) != len(self.nodes):
            raise ValueError("Pipeline DAG contains a cycle (excluding loop-back edges)")

        return result

    def get_next_nodes(
        self, current_node: str, result_data: dict[str, Any]
    ) -> list[str]:
        """Get the next nodes to execute based on current node result."""
        next_nodes = []
        for edge in self._adjacency.get(current_node, []):
            if edge.condition is None or edge.condition(result_data):
                next_nodes.append(edge.to_node)
        return next_nodes

    def get_predecessors(self, node_name: str) -> list[str]:
        """Get all predecessor node names."""
        return [
            edge.from_node
            for edge in self.edges
            if edge.to_node == node_name
        ]

    @classmethod
    def build_chapter_dag(cls) -> PipelineDAG:
        """Build the standard chapter writing DAG.

        Flow: radar → architect → context → writer → settler → auditor
              → [pass] finalize
              → [revise] reviser → auditor (loop-back, max 3)
        Note: pacing_controller parallel branch deferred to iteration 3.
        """
        dag = cls()

        dag.add_node(PipelineNode(name="radar", agent_name="radar"))
        dag.add_node(PipelineNode(name="architect", agent_name="architect"))
        dag.add_node(PipelineNode(name="context", agent_name="context"))
        dag.add_node(PipelineNode(name="writer", agent_name="writer"))
        dag.add_node(PipelineNode(name="settler", agent_name="settler"))
        dag.add_node(PipelineNode(name="auditor", agent_name="auditor", max_loops=3))
        dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
        dag.add_node(PipelineNode(
            name="finalize", agent_name="finalize",
            params={"action": "finalize"},
        ))

        # Linear flow: radar → architect → context → writer → settler → auditor
        dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))
        dag.add_edge(PipelineEdge(from_node="architect", to_node="context"))
        dag.add_edge(PipelineEdge(from_node="context", to_node="writer"))
        dag.add_edge(PipelineEdge(from_node="writer", to_node="settler"))
        dag.add_edge(PipelineEdge(from_node="settler", to_node="auditor"))

        # Conditional branching from auditor
        dag.add_edge(PipelineEdge(
            from_node="auditor",
            to_node="finalize",
            condition=lambda r: r.get("recommendation") == "pass",
        ))
        dag.add_edge(PipelineEdge(
            from_node="auditor",
            to_node="reviser",
            condition=lambda r: r.get("recommendation") in ("revise", "rework"),
        ))

        # Loop-back: reviser → auditor (marked as loop-back, excluded from topo sort)
        dag.add_edge(PipelineEdge(
            from_node="reviser", to_node="auditor", is_loop_back=True
        ))

        return dag
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestration/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(iter2): implement Pipeline DAG with topological sort and conditions"
```

---

### Task 15: Pipeline Executor (Runtime Engine)

**Files:**
- Create: `backend/app/orchestration/executor.py`
- Create: `backend/tests/test_executor.py`

The executor runs agents through the DAG, handling state, conditions, and loops.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.orchestration.executor import PipelineExecutor
from app.orchestration.pipeline import PipelineDAG, PipelineNode, PipelineEdge
from app.schemas.agent import AgentContext, AgentResult


def _make_simple_dag():
    """a → b → c (linear)"""
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="agent_a"))
    dag.add_node(PipelineNode(name="b", agent_name="agent_b"))
    dag.add_node(PipelineNode(name="c", agent_name="agent_c"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="c"))
    return dag


def _make_success_result(name: str, data: dict = None):
    return AgentResult(
        agent_name=name, success=True, data=data or {"status": "ok"}, duration_ms=10
    )


def _make_agent_registry(results: dict[str, AgentResult]):
    """Create a mock agent registry that returns pre-configured results."""
    registry = {}
    for agent_name, result in results.items():
        agent = AsyncMock()
        agent.execute = AsyncMock(return_value=result)
        registry[agent_name] = agent
    return registry


async def test_executor_linear_pipeline():
    dag = _make_simple_dag()
    agents = _make_agent_registry({
        "agent_a": _make_success_result("a"),
        "agent_b": _make_success_result("b"),
        "agent_c": _make_success_result("c"),
    })
    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    results = await executor.run(ctx)

    assert len(results) == 3
    assert all(r.success for r in results)
    assert [r.agent_name for r in results] == ["a", "b", "c"]


async def test_executor_stops_on_failure():
    dag = _make_simple_dag()
    agents = _make_agent_registry({
        "agent_a": _make_success_result("a"),
        "agent_b": AgentResult(agent_name="b", success=False, error="LLM failed"),
        "agent_c": _make_success_result("c"),
    })
    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    results = await executor.run(ctx)

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False


async def test_executor_conditional_branch():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="done"))
    dag.add_edge(PipelineEdge(
        from_node="auditor", to_node="done",
        condition=lambda r: r.get("recommendation") == "pass",
    ))
    dag.add_edge(PipelineEdge(
        from_node="auditor", to_node="reviser",
        condition=lambda r: r.get("recommendation") == "revise",
    ))

    agents = _make_agent_registry({
        "auditor": _make_success_result("auditor", {"recommendation": "pass"}),
        "reviser": _make_success_result("reviser"),
        "done": _make_success_result("done"),
    })
    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    results = await executor.run(ctx)

    # Should go auditor → done (skip reviser)
    names = [r.agent_name for r in results]
    assert "auditor" in names
    assert "done" in names
    assert "reviser" not in names


async def test_executor_loop():
    """Auditor → Reviser → Auditor (pass on second audit)."""
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor", max_loops=3))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="done"))
    dag.add_edge(PipelineEdge(
        from_node="auditor", to_node="reviser",
        condition=lambda r: r.get("recommendation") == "revise",
    ))
    dag.add_edge(PipelineEdge(
        from_node="auditor", to_node="done",
        condition=lambda r: r.get("recommendation") == "pass",
    ))
    dag.add_edge(PipelineEdge(from_node="reviser", to_node="auditor", is_loop_back=True))

    call_count = {"auditor": 0}

    async def auditor_execute(ctx):
        call_count["auditor"] += 1
        if call_count["auditor"] == 1:
            return _make_success_result("auditor", {"recommendation": "revise"})
        return _make_success_result("auditor", {"recommendation": "pass"})

    auditor_mock = AsyncMock()
    auditor_mock.execute = auditor_execute

    agents = {
        "auditor": auditor_mock,
        "reviser": _make_agent_registry({"reviser": _make_success_result("reviser")})["reviser"],
        "done": _make_agent_registry({"done": _make_success_result("done")})["done"],
    }
    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    results = await executor.run(ctx)

    names = [r.agent_name for r in results]
    # Should be: auditor(revise) → reviser → auditor(pass) → done
    assert names == ["auditor", "reviser", "auditor", "done"]


async def test_executor_node_results_stored():
    dag = _make_simple_dag()
    agents = _make_agent_registry({
        "agent_a": _make_success_result("a", {"key": "value"}),
        "agent_b": _make_success_result("b"),
        "agent_c": _make_success_result("c"),
    })
    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    await executor.run(ctx)

    assert "a" in executor.node_results
    assert executor.node_results["a"].data["key"] == "value"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_executor.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement PipelineExecutor**

```python
# backend/app/orchestration/executor.py
"""Pipeline executor: runs agents through the DAG with state, conditions, and loops."""

from __future__ import annotations

from typing import Any, Protocol

from app.orchestration.pipeline import PipelineDAG
from app.schemas.agent import AgentContext, AgentResult


class AgentProtocol(Protocol):
    async def execute(self, context: AgentContext) -> AgentResult: ...


class PipelineExecutor:
    """Executes a PipelineDAG by running agents in topological order.

    Features:
    - Conditional branching (edges with conditions)
    - Loop support (nodes with max_loops > 1)
    - Stops on agent failure
    - Stores results per node for downstream access
    """

    def __init__(
        self,
        dag: PipelineDAG,
        agents: dict[str, AgentProtocol],
    ):
        self.dag = dag
        self.agents = agents
        self.node_results: dict[str, AgentResult] = {}
        self._loop_counts: dict[str, int] = {}

    async def run(self, context: AgentContext) -> list[AgentResult]:
        """Execute the pipeline from root nodes to completion."""
        results: list[AgentResult] = []

        # Find start nodes (no predecessors)
        start_nodes = [
            name
            for name in self.dag.nodes
            if not self.dag.get_predecessors(name)
        ]

        # BFS-style execution following DAG edges
        queue = list(start_nodes)
        visited: set[str] = set()

        while queue:
            node_name = queue.pop(0)

            # Skip if already visited (unless it's a loop node within limits)
            if node_name in visited:
                node = self.dag.nodes[node_name]
                loop_count = self._loop_counts.get(node_name, 0)
                if loop_count >= node.max_loops:
                    continue
            else:
                visited.add(node_name)

            # Track loop count
            self._loop_counts[node_name] = self._loop_counts.get(node_name, 0) + 1

            # Execute agent
            node = self.dag.nodes[node_name]
            agent = self.agents.get(node.agent_name)
            if agent is None:
                results.append(
                    AgentResult(
                        agent_name=node_name,
                        success=False,
                        error=f"Agent '{node.agent_name}' not found",
                    )
                )
                break

            # Merge pipeline data from previous node results
            ctx = self._build_context(context, node_name)
            result = await agent.execute(ctx)
            results.append(result)
            self.node_results[node_name] = result

            if not result.success:
                break

            # Determine next nodes based on conditions
            next_nodes = self.dag.get_next_nodes(node_name, result.data)
            queue.extend(next_nodes)

        return results

    def _build_context(
        self, base_context: AgentContext, node_name: str
    ) -> AgentContext:
        """Build context for a node, merging results from predecessors."""
        pipeline_data = dict(base_context.pipeline_data)

        # Add results from all completed nodes
        for prev_name, prev_result in self.node_results.items():
            if prev_result.success:
                pipeline_data[prev_name] = prev_result.data

        return AgentContext(
            project_id=base_context.project_id,
            chapter_id=base_context.chapter_id,
            volume_id=base_context.volume_id,
            pipeline_data=pipeline_data,
            params=self.dag.nodes[node_name].params,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_executor.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestration/executor.py backend/tests/test_executor.py
git commit -m "feat(iter2): implement PipelineExecutor with conditions and loops"
```

---

### Task 16: Celery Task Wrappers + Pipeline Service

**Files:**
- Create: `backend/app/jobs/writing.py`
- Create: `backend/app/jobs/audit.py`
- Create: `backend/app/services/pipeline_service.py`
- Create: `backend/tests/test_pipeline_service.py`

Celery tasks wrap pipeline execution; PipelineService orchestrates DB + agents.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pipeline_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.job_run import JobRun
from app.services.pipeline_service import PipelineService


async def _create_project(db: AsyncSession) -> Project:
    project = Project(title="Test", genre="xuanhuan", status="active", settings={})
    db.add(project)
    await db.flush()
    return project


async def test_create_job_run(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)

    job = await svc.create_job_run(project.id, "pipeline_write")

    assert job.project_id == project.id
    assert job.job_type == "pipeline_write"
    assert job.status == "pending"


async def test_update_job_status(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "pipeline_write")

    updated = await svc.update_job_status(job.id, "running")
    assert updated.status == "running"

    updated = await svc.update_job_status(job.id, "completed")
    assert updated.status == "completed"


async def test_get_job_run(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "pipeline_write")

    found = await svc.get_job_run(job.id)
    assert found is not None
    assert found.id == job.id


async def test_get_job_run_not_found(db_session: AsyncSession):
    svc = PipelineService(db_session)
    found = await svc.get_job_run(uuid4())
    assert found is None


async def test_update_job_with_result(db_session: AsyncSession):
    project = await _create_project(db_session)
    svc = PipelineService(db_session)
    job = await svc.create_job_run(project.id, "audit")

    updated = await svc.update_job_status(
        job.id,
        "completed",
        result={"pass_rate": 0.95},
        agent_chain=["radar", "auditor"],
    )
    assert updated.result == {"pass_rate": 0.95}
    assert updated.agent_chain == ["radar", "auditor"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pipeline_service.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement PipelineService**

```python
# backend/app/services/pipeline_service.py
"""Pipeline service: manages job runs and orchestrates pipeline execution."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun


class PipelineService:
    """Service layer for pipeline job management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job_run(
        self, project_id: UUID, job_type: str
    ) -> JobRun:
        job = JobRun(
            project_id=project_id,
            job_type=job_type,
            status="pending",
            agent_chain=[],
            result={},
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job_run(self, job_id: UUID) -> JobRun | None:
        stmt = select(JobRun).where(JobRun.id == job_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_job_status(
        self,
        job_id: UUID,
        status: str,
        result: dict | None = None,
        error_message: str | None = None,
        agent_chain: list[str] | None = None,
    ) -> JobRun:
        job = await self.get_job_run(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job.status = status

        if status == "running" and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed", "cancelled"):
            job.finished_at = datetime.now(timezone.utc)

        if result is not None:
            job.result = result
        if error_message is not None:
            job.error_message = error_message
        if agent_chain is not None:
            job.agent_chain = agent_chain

        await self.db.flush()
        return job
```

- [ ] **Step 4: Implement Celery task wrappers**

```python
# backend/app/jobs/writing.py
"""Celery tasks for writing pipeline (writing queue)."""

from app.jobs.celery_app import celery_app


@celery_app.task(queue="writing", bind=True, max_retries=2)
def run_chapter_pipeline(self, project_id: str, chapter_id: str, job_id: str):
    """Run the full chapter writing pipeline as a Celery task.

    This is a sync wrapper that delegates to the async pipeline executor.
    Actual implementation will be connected in the API layer.
    """
    # Placeholder: will be wired to PipelineExecutor in the API layer
    return {"status": "completed", "job_id": job_id}
```

```python
# backend/app/jobs/audit.py
"""Celery tasks for audit pipeline (audit queue)."""

from app.jobs.celery_app import celery_app


@celery_app.task(queue="audit", bind=True, max_retries=2)
def run_chapter_audit(self, chapter_id: str, draft_id: str, job_id: str, mode: str = "full"):
    """Run chapter audit as a Celery task."""
    return {"status": "completed", "job_id": job_id}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pipeline_service.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pipeline_service.py backend/app/jobs/writing.py backend/app/jobs/audit.py backend/tests/test_pipeline_service.py
git commit -m "feat(iter2): implement PipelineService + Celery task wrappers"
```

---

### Task 17: Pipeline API Endpoints + Truth File API

**Files:**
- Create: `backend/app/api/pipeline.py`
- Create: `backend/app/api/truth_files.py`
- Create: `backend/app/schemas/pipeline.py`
- Create: `backend/app/schemas/truth_file.py`
- Modify: `backend/app/main.py` (register new routers)
- Create: `backend/tests/test_api_pipeline.py`
- Create: `backend/tests/test_api_truth_files.py`

- [ ] **Step 1: Create schemas**

```python
# backend/app/schemas/pipeline.py
"""Schemas for pipeline API endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PipelineRunRequest(BaseModel):
    chapter_id: UUID
    mode: str = "auto"  # auto / semi


class JobRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    job_type: str
    status: str
    agent_chain: list[str]
    result: dict[str, Any]
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
```

```python
# backend/app/schemas/truth_file.py
"""Schemas for truth file API endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TruthFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    file_type: str
    content: dict[str, Any]
    version: int
    created_at: datetime


class TruthFileHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    truth_file_id: UUID
    version: int
    content: dict[str, Any]
    changed_by_chapter_id: UUID | None = None
    created_at: datetime
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_api_pipeline.py
from uuid import uuid4


async def _create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers
    )
    return resp.json()["id"]


async def test_create_job_run(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.post(
        f"/api/projects/{pid}/pipeline/write-chapter",
        json={"chapter_id": str(uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["job_type"] == "pipeline_write"


async def test_get_job_status(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    create_resp = await client.post(
        f"/api/projects/{pid}/pipeline/write-chapter",
        json={"chapter_id": str(uuid4())},
        headers=auth_headers,
    )
    job_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/pipeline/jobs/{job_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


async def test_get_job_not_found(client, auth_headers):
    resp = await client.get(
        f"/api/pipeline/jobs/{uuid4()}", headers=auth_headers
    )
    assert resp.status_code == 404
```

```python
# backend/tests/test_api_truth_files.py

async def _create_project(client, auth_headers):
    resp = await client.post(
        "/api/projects", json={"title": "Test", "genre": "xuanhuan"}, headers=auth_headers
    )
    return resp.json()["id"]


async def test_list_truth_files(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(
        f"/api/projects/{pid}/truth-files", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10  # project creation initializes 10 truth files


async def test_get_truth_file(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(
        f"/api/projects/{pid}/truth-files/story_bible", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_type"] == "story_bible"
    assert data["version"] == 1


async def test_get_truth_file_not_found(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(
        f"/api/projects/{pid}/truth-files/nonexistent", headers=auth_headers
    )
    assert resp.status_code == 404


async def test_get_truth_file_history(client, auth_headers):
    pid = await _create_project(client, auth_headers)
    resp = await client.get(
        f"/api/projects/{pid}/truth-files/story_bible/history", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_api_pipeline.py tests/test_api_truth_files.py -v`
Expected: FAIL (ImportError / 404 route not found)

- [ ] **Step 4: Implement Pipeline API**

```python
# backend/app/api/pipeline.py
"""Pipeline API endpoints: start/status/control for writing jobs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.schemas.pipeline import JobRunResponse, PipelineRunRequest
from app.services.pipeline_service import PipelineService

router = APIRouter(
    prefix="/api", tags=["pipeline"], dependencies=[Depends(verify_token)]
)


@router.post(
    "/projects/{project_id}/pipeline/write-chapter",
    response_model=JobRunResponse,
    status_code=202,
)
async def start_write_chapter(
    project_id: UUID,
    body: PipelineRunRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = PipelineService(db)
    job = await svc.create_job_run(project_id, "pipeline_write")
    # TODO: dispatch Celery task with job.id
    return job


@router.get("/pipeline/jobs/{job_id}", response_model=JobRunResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = PipelineService(db)
    job = await svc.get_job_run(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/pipeline/jobs/{job_id}/cancel", response_model=JobRunResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = PipelineService(db)
    job = await svc.get_job_run(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Job already finished")
    updated = await svc.update_job_status(job_id, "cancelled")
    return updated
```

- [ ] **Step 5: Implement Truth File API**

```python
# backend/app/api/truth_files.py
"""Truth File API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_token
from app.engines.state_manager import StateManager
from app.schemas.truth_file import TruthFileHistoryResponse, TruthFileResponse

router = APIRouter(
    prefix="/api", tags=["truth-files"], dependencies=[Depends(verify_token)]
)


@router.get(
    "/projects/{project_id}/truth-files",
    response_model=list[TruthFileResponse],
)
async def list_truth_files(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    mgr = StateManager(db)
    return await mgr.list_truth_files(project_id)


@router.get(
    "/projects/{project_id}/truth-files/{file_type}",
    response_model=TruthFileResponse,
)
async def get_truth_file(
    project_id: UUID,
    file_type: str,
    db: AsyncSession = Depends(get_db),
):
    mgr = StateManager(db)
    tf = await mgr.get_truth_file(project_id, file_type)
    if tf is None:
        raise HTTPException(status_code=404, detail=f"Truth file '{file_type}' not found")
    return tf


@router.get(
    "/projects/{project_id}/truth-files/{file_type}/history",
    response_model=list[TruthFileHistoryResponse],
)
async def get_truth_file_history(
    project_id: UUID,
    file_type: str,
    db: AsyncSession = Depends(get_db),
):
    mgr = StateManager(db)
    return await mgr.get_history(project_id, file_type)
```

- [ ] **Step 6: Register new routers in main.py**

Add to `backend/app/main.py`, in the router registration section:

```python
from app.api.pipeline import router as pipeline_router
from app.api.truth_files import router as truth_files_router

app.include_router(pipeline_router)
app.include_router(truth_files_router)
```

- [ ] **Step 7: Run tests**

Run: `cd backend && pytest tests/test_api_pipeline.py tests/test_api_truth_files.py -v`
Expected: 7 passed (3 pipeline + 4 truth files)

- [ ] **Step 8: Run all tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/pipeline.py backend/app/api/truth_files.py backend/app/schemas/pipeline.py backend/app/schemas/truth_file.py backend/app/main.py backend/tests/test_api_pipeline.py backend/tests/test_api_truth_files.py
git commit -m "feat(iter2): add Pipeline + Truth File API endpoints"
```

---

### Task 18: Agent Registry + Full Integration Test

**Files:**
- Modify: `backend/app/agents/__init__.py`
- Create: `backend/tests/test_integration_pipeline.py`

Wire up all agents into a registry and run a full pipeline integration test with mocked LLM.

- [ ] **Step 1: Update agents `__init__.py`**

```python
# backend/app/agents/__init__.py
"""Agent registry: maps agent names to agent classes."""

from app.agents.architect import ArchitectAgent
from app.agents.auditor import AuditorAgent
from app.agents.base import BaseAgent
from app.agents.context_agent import ContextAgent
from app.agents.radar import RadarAgent
from app.agents.reviser import ReviserAgent
from app.agents.settler import SettlerAgent
from app.agents.writer import WriterAgent

AGENT_CLASSES = {
    "radar": RadarAgent,
    "architect": ArchitectAgent,
    "context": ContextAgent,
    "writer": WriterAgent,
    "settler": SettlerAgent,
    "auditor": AuditorAgent,
    "reviser": ReviserAgent,
}

__all__ = [
    "BaseAgent",
    "RadarAgent",
    "ArchitectAgent",
    "ContextAgent",
    "WriterAgent",
    "SettlerAgent",
    "AuditorAgent",
    "ReviserAgent",
    "AGENT_CLASSES",
]
```

- [ ] **Step 2: Write integration test**

```python
# backend/tests/test_integration_pipeline.py
"""Integration test: full chapter pipeline with mocked LLM."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents import AGENT_CLASSES
from app.orchestration.executor import PipelineExecutor
from app.orchestration.pipeline import PipelineDAG, PipelineEdge, PipelineNode
from app.schemas.agent import AgentContext, AgentResult


def _make_finalize_agent():
    """A simple no-op agent for the finalize node."""
    agent = AsyncMock()
    agent.execute = AsyncMock(
        return_value=AgentResult(agent_name="finalize", success=True, data={"status": "finalized"})
    )
    return agent


def _make_mock_context_agent():
    """Mock ContextAgent that returns assembled context without DB."""
    agent = AsyncMock()
    agent.execute = AsyncMock(
        return_value=AgentResult(
            agent_name="context", success=True,
            data={"system_prompt": "You are a writer.", "user_prompt": "Write.", "context_tokens": 50, "sections": {}},
        )
    )
    return agent


def _make_mock_provider():
    """Create a mock provider that returns different responses based on call order."""
    provider = AsyncMock()
    responses = [
        # Radar
        json.dumps({"next_action": "write_chapter", "reasoning": "Chapter planned"}),
        # Architect
        json.dumps({"stage": "scene_cards", "content": {"scenes": []}}),
        # Writer Phase1
        "叶辰站在青云宗大门前，心中涌起无限感慨。",
        # Writer Phase2
        json.dumps({"new_entities": [], "state_changes": {}, "summary": "叶辰到达"}),
        # Settler
        json.dumps({"extracted_entities": [], "truth_file_updates": {}}),
        # Auditor
        json.dumps({
            "scores": {"consistency": 8, "narrative": 7, "style": 8},
            "pass_rate": 1.0,
            "has_blocking": False,
            "issues": [],
            "recommendation": "pass",
        }),
    ]
    call_idx = {"n": 0}

    async def mock_chat(**kwargs):
        from app.providers.base import ChatResponse
        idx = call_idx["n"]
        call_idx["n"] += 1
        content = responses[idx] if idx < len(responses) else "{}"
        return ChatResponse(content=content, model="mock", usage={})

    provider.chat = mock_chat
    return provider


async def test_full_pipeline_pass():
    """Test a complete pipeline execution where auditor passes on first try."""
    provider = _make_mock_provider()

    # Build a simplified linear DAG (no conditional branching for this test)
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="architect", agent_name="architect"))
    dag.add_node(PipelineNode(name="context", agent_name="context"))
    dag.add_node(PipelineNode(name="writer", agent_name="writer"))
    dag.add_node(PipelineNode(name="settler", agent_name="settler"))
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))

    dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))
    dag.add_edge(PipelineEdge(from_node="architect", to_node="context"))
    dag.add_edge(PipelineEdge(from_node="context", to_node="writer"))
    dag.add_edge(PipelineEdge(from_node="writer", to_node="settler"))
    dag.add_edge(PipelineEdge(from_node="settler", to_node="auditor"))

    # Create agent instances (ContextAgent mocked since no DB in unit test)
    agents = {}
    for name, cls in AGENT_CLASSES.items():
        if name == "context":
            agents[name] = _make_mock_context_agent()
        else:
            agents[name] = cls(provider=provider)

    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    results = await executor.run(ctx)

    # All 6 agents should execute successfully
    assert len(results) == 6
    assert all(r.success for r in results), [
        f"{r.agent_name}: {r.error}" for r in results if not r.success
    ]
    agent_names = [r.agent_name for r in results]
    assert agent_names == ["radar", "architect", "context", "writer", "settler", "auditor"]


async def test_pipeline_agent_failure_stops():
    """Test that pipeline stops when an agent fails."""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=Exception("API error"))

    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="writer", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="radar", to_node="writer"))

    agents = {
        "radar": AGENT_CLASSES["radar"](provider=provider),
        "writer": AGENT_CLASSES["writer"](provider=provider),
    }
    # Force 1 retry to speed up test
    for a in agents.values():
        a.max_retries = 1

    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4())

    results = await executor.run(ctx)

    # Radar should fail, writer should never execute
    assert len(results) == 1
    assert results[0].success is False


async def test_pipeline_audit_revise_loop():
    """Test auditor → reviser → auditor loop with build_chapter_dag."""
    call_count = {"n": 0}

    async def mock_chat(**kwargs):
        from app.providers.base import ChatResponse
        call_count["n"] += 1
        n = call_count["n"]
        if n <= 2:
            return ChatResponse(
                content=json.dumps({"next_action": "write", "stage": "test", "content": {}}),
                model="mock", usage={},
            )
        if n == 3:
            return ChatResponse(content="Story text.", model="mock", usage={})
        if n == 4:
            return ChatResponse(
                content=json.dumps({"summary": "test"}), model="mock", usage={}
            )
        if n == 5:
            return ChatResponse(
                content=json.dumps({"extracted_entities": [], "truth_file_updates": {}}),
                model="mock", usage={},
            )
        if n == 6:
            # Auditor first: revise
            return ChatResponse(
                content=json.dumps({
                    "scores": {"quality": 4}, "pass_rate": 0.3, "has_blocking": False,
                    "issues": [{"dimension": "quality", "message": "needs work", "severity": "error"}],
                    "recommendation": "revise",
                }),
                model="mock", usage={},
            )
        if n == 7:
            return ChatResponse(content="Revised text.", model="mock", usage={})
        # Auditor second: pass
        return ChatResponse(
            content=json.dumps({
                "scores": {"quality": 8}, "pass_rate": 1.0, "has_blocking": False,
                "issues": [], "recommendation": "pass",
            }),
            model="mock", usage={},
        )

    provider = AsyncMock()
    provider.chat = mock_chat

    dag = PipelineDAG.build_chapter_dag()

    agents = {}
    for name, cls in AGENT_CLASSES.items():
        if name == "context":
            agents[name] = _make_mock_context_agent()
        else:
            agent = cls(provider=provider)
            agent.max_retries = 1
            agents[name] = agent
    agents["finalize"] = _make_finalize_agent()

    executor = PipelineExecutor(dag, agents)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())

    results = await executor.run(ctx)

    names = [r.agent_name for r in results]
    assert "reviser" in names
    assert names.count("auditor") == 2
    assert names[-1] == "finalize"
```

- [ ] **Step 3: Run integration test**

Run: `cd backend && pytest tests/test_integration_pipeline.py -v`
Expected: 3 passed

- [ ] **Step 4: Run ALL tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass (25 existing + new tests from iteration 2)

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/__init__.py backend/tests/test_integration_pipeline.py
git commit -m "feat(iter2): add agent registry + full pipeline integration tests"
```

---

## Summary

| Task | Component | Files | Tests |
|------|-----------|-------|-------|
| 1 | Dependencies + dirs | pyproject.toml + 4 __init__.py | — |
| 2 | Agent schemas | schemas/agent.py | 13 tests |
| 3 | BaseAgent | agents/base.py | 5 tests |
| 4 | State Manager | engines/state_manager.py | 6 tests |
| 5 | World Model | engines/world_model.py | 5 tests |
| 6 | Context Filter | engines/context_filter.py | 4 tests |
| 7 | Celery + Docker | jobs/celery_app.py + docker-compose | 4 tests |
| 8 | RadarAgent | agents/radar.py | 4 tests |
| 9 | ArchitectAgent | agents/architect.py | 4 tests |
| 10 | ContextAgent | agents/context_agent.py | 3 tests |
| 11 | WriterAgent | agents/writer.py | 4 tests |
| 12 | SettlerAgent | agents/settler.py | 3 tests |
| 13 | Auditor+Reviser | agents/auditor.py + reviser.py | 5 tests |
| 14 | Pipeline DAG | orchestration/pipeline.py | 7 tests |
| 15 | Pipeline Executor | orchestration/executor.py | 5 tests |
| 16 | Pipeline Service | services/pipeline_service.py + jobs/ | 5 tests |
| 17 | API Endpoints | api/pipeline.py + api/truth_files.py | 7 tests |
| 18 | Integration | agents/__init__.py + integration test | 3 tests |

**Total: 18 tasks, ~87 new tests**
