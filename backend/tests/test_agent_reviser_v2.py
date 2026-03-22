# backend/tests/test_agent_reviser_v2.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.agents.reviser import ReviserAgent
from app.providers.base import ChatResponse
from app.schemas.agent import AgentContext, ReviserOutput


def _make_provider(response_text: str):
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=ChatResponse(
        content=response_text, model="gpt-4o",
        usage={"input_tokens": 100, "output_tokens": 200},
    ))
    return provider


def _make_reviser_response():
    return json.dumps({
        "revised_content": "修改后的文本内容。" * 20,
        "changes_summary": "Removed AI traces, improved flow",
        "word_count": 200,
    })


async def test_reviser_anti_detect_mode():
    """Anti-detect mode should include fatigue words in prompt."""
    provider = _make_provider(_make_reviser_response())
    agent = ReviserAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "他不禁缓缓叹了口气。" * 20},
            "auditor": {"issues": [{"dimension": "ai_trace_detection", "message": "High AI density"}]},
            "draft_id": str(uuid4()),
        },
        params={"mode": "anti-detect"},
    )
    result = await agent.execute(ctx)
    assert result.success

    # Verify fatigue words were included in the prompt
    call_args = provider.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    prompt_text = " ".join(m.content for m in messages)
    assert "疲劳词" in prompt_text or "禁止" in prompt_text or "不使用" in prompt_text


async def test_reviser_polish_mode():
    """Polish mode should work without De-AI integration."""
    provider = _make_provider(_make_reviser_response())
    agent = ReviserAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "一些文本内容。" * 20},
            "auditor": {"issues": []},
            "draft_id": str(uuid4()),
        },
        params={"mode": "polish"},
    )
    result = await agent.execute(ctx)
    assert result.success


async def test_reviser_includes_audit_issues():
    """All modes should include audit issues in prompt."""
    provider = _make_provider(_make_reviser_response())
    agent = ReviserAgent(provider, model="gpt-4o")
    issues = [
        {"dimension": "ooc_detection", "message": "Character acted out of character", "severity": "error"},
    ]
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "文本" * 50},
            "auditor": {"issues": issues},
            "draft_id": str(uuid4()),
        },
        params={"mode": "spot-fix"},
    )
    result = await agent.execute(ctx)
    assert result.success

    call_args = provider.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    prompt_text = " ".join(m.content for m in messages)
    assert "ooc_detection" in prompt_text or "out of character" in prompt_text.lower()


async def test_reviser_output_schema():
    """Output should match ReviserOutput schema."""
    provider = _make_provider(_make_reviser_response())
    agent = ReviserAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        pipeline_data={
            "writer": {"phase1_content": "文本" * 50},
            "auditor": {"issues": []},
            "draft_id": str(uuid4()),
        },
        params={"mode": "polish"},
    )
    result = await agent.execute(ctx)
    out = ReviserOutput(**result.data)
    assert out.word_count > 0
    assert len(out.revised_content) > 0
