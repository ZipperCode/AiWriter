# backend/tests/test_agent_auditor_v2.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.auditor import AuditorAgent
from app.providers.base import ChatMessage, ChatResponse
from app.schemas.agent import AgentContext, AuditorOutput
from app.engines.quality_audit import AuditRunner, DimensionResult


def _make_provider(response_text: str):
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=ChatResponse(
        content=response_text, model="gpt-4o",
        usage={"input_tokens": 100, "output_tokens": 50},
    ))
    return provider


def _make_llm_audit_response():
    """Mock LLM response for non-deterministic dimensions."""
    scores = {}
    for dim_id in range(1, 34):
        # Skip deterministic dims (5, 7, 26, 27, 28) -- handled by AuditRunner
        if dim_id in (5, 7, 26, 27, 28):
            continue
        scores[str(dim_id)] = {"score": 8.0, "message": "Looks good"}
    return json.dumps(scores)


async def test_auditor_uses_audit_runner():
    """Auditor should run deterministic checks via AuditRunner."""
    provider = _make_provider(_make_llm_audit_response())
    agent = AuditorAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "他走向前方。" * 50},
            "draft_id": str(uuid4()),
        },
        params={"mode": "full"},
    )
    result = await agent.execute(ctx)
    assert result.success
    assert "scores" in result.data
    assert "pass_rate" in result.data
    assert "recommendation" in result.data


async def test_auditor_quick_mode():
    """Quick mode should only run deterministic checks (no LLM)."""
    provider = _make_provider("")  # Should not be called
    agent = AuditorAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "正常的文本内容。" * 30},
            "draft_id": str(uuid4()),
        },
        params={"mode": "quick"},
    )
    result = await agent.execute(ctx)
    assert result.success
    # Quick mode should have scores for deterministic dimensions only
    scores = result.data.get("scores", {})
    # Should have dim 5, 7, 26, 27, 28
    assert len(scores) == 5


async def test_auditor_33_dimensions_full():
    """Full mode should return scores for all 33 dimensions."""
    provider = _make_provider(_make_llm_audit_response())
    agent = AuditorAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "正常文本。" * 50},
            "draft_id": str(uuid4()),
        },
        params={"mode": "full"},
    )
    result = await agent.execute(ctx)
    assert result.success
    scores = result.data.get("scores", {})
    assert len(scores) == 33


async def test_auditor_output_schema():
    """Auditor output should match AuditorOutput schema."""
    provider = _make_provider(_make_llm_audit_response())
    agent = AuditorAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "文本" * 100},
            "draft_id": str(uuid4()),
        },
        params={"mode": "full"},
    )
    result = await agent.execute(ctx)
    assert result.success
    out = AuditorOutput(**result.data)
    assert 0 <= out.pass_rate <= 1.0
    assert out.recommendation in ("pass", "revise", "rework")
