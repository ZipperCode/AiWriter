import json
from unittest.mock import AsyncMock
from uuid import uuid4
from app.agents.writer import WriterAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(*responses: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    side_effects = [ChatResponse(content=r, model="claude-sonnet", usage={}) for r in responses]
    provider.chat = AsyncMock(side_effect=side_effects)
    return provider


async def test_writer_execute_success():
    creative_text = "叶辰踏入了青云宗的大门。"
    settlement = json.dumps({"new_entities": [{"name": "青云宗", "type": "faction"}], "state_changes": {"location": "青云宗"}, "summary": "叶辰进入青云宗"})
    provider = _mock_provider(creative_text, settlement)
    agent = WriterAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), params={"target_words": 50}, pipeline_data={"context": {"system_prompt": "You are a writer.", "user_prompt": "Write chapter 1."}})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["phase1_content"] == creative_text
    assert result.data["word_count"] > 0


async def test_writer_phase1_only():
    provider = _mock_provider("Some story text.", '{"summary": "test"}')
    agent = WriterAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["phase1_content"] == "Some story text."


async def test_writer_build_messages_with_context():
    provider = _mock_provider("text", "{}")
    agent = WriterAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"context": {"system_prompt": "Custom system prompt.", "user_prompt": "Custom user prompt."}})
    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert "Custom system prompt" in messages[0].content
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
