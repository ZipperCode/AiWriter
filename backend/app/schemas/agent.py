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
