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
