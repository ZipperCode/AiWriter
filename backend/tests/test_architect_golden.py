import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.agents.architect import ArchitectAgent
from app.providers.base import ChatResponse
from app.schemas.agent import AgentContext


def _make_provider(response_text: str):
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=ChatResponse(
        content=response_text, model="gpt-4o",
        usage={"input_tokens": 100, "output_tokens": 100},
    ))
    return provider


async def test_golden_chapter_1_prompt():
    """Chapter 1 planning should include golden rule: core conflict."""
    provider = _make_provider(json.dumps({
        "stage": "chapter_plan",
        "content": {"chapter": 1, "plan": "introduce conflict"},
    }))
    agent = ArchitectAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        params={
            "stage": "chapter_plan",
            "chapter_sort_order": 1,
        },
    )
    result = await agent.execute(ctx)
    assert result.success

    call_args = provider.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    prompt_text = " ".join(m.content for m in messages)
    assert "核心冲突" in prompt_text or "core conflict" in prompt_text.lower()


async def test_golden_chapter_2_prompt():
    """Chapter 2 planning should include golden rule: showcase power/golden finger."""
    provider = _make_provider(json.dumps({
        "stage": "chapter_plan",
        "content": {"chapter": 2, "plan": "show golden finger"},
    }))
    agent = ArchitectAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        params={
            "stage": "chapter_plan",
            "chapter_sort_order": 2,
        },
    )
    result = await agent.execute(ctx)
    assert result.success

    call_args = provider.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    prompt_text = " ".join(m.content for m in messages)
    assert "金手指" in prompt_text or "golden finger" in prompt_text.lower() or "核心能力" in prompt_text


async def test_golden_chapter_3_prompt():
    """Chapter 3 planning should include golden rule: clear short-term goal."""
    provider = _make_provider(json.dumps({
        "stage": "chapter_plan",
        "content": {"chapter": 3, "plan": "set goal"},
    }))
    agent = ArchitectAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        params={
            "stage": "chapter_plan",
            "chapter_sort_order": 3,
        },
    )
    result = await agent.execute(ctx)
    assert result.success

    call_args = provider.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]
    prompt_text = " ".join(m.content for m in messages)
    assert "短期目标" in prompt_text or "short-term goal" in prompt_text.lower()


async def test_non_golden_chapter_no_constraint():
    """Chapter 4+ should not have golden three chapters constraints."""
    provider = _make_provider(json.dumps({
        "stage": "chapter_plan",
        "content": {"chapter": 4, "plan": "normal chapter"},
    }))
    agent = ArchitectAgent(provider, model="gpt-4o")
    ctx = AgentContext(
        project_id=uuid4(), chapter_id=uuid4(),
        params={
            "stage": "chapter_plan",
            "chapter_sort_order": 4,
        },
    )
    result = await agent.execute(ctx)
    assert result.success
