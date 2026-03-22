import json
from unittest.mock import AsyncMock
from uuid import uuid4
from app.agents.architect import ArchitectAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response_content: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(return_value=ChatResponse(content=response_content, model="gpt-4o", usage={}))
    return provider


async def test_architect_chapter_plan():
    response = json.dumps({"stage": "chapter_plan", "content": {"chapters": [{"title": "Chapter 1", "summary": "Hero arrives", "sort_order": 1}, {"title": "Chapter 2", "summary": "First trial", "sort_order": 2}]}})
    provider = _mock_provider(response)
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), volume_id=uuid4(), params={"stage": "chapter_plan"})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["stage"] == "chapter_plan"
    assert len(result.data["content"]["chapters"]) == 2


async def test_architect_scene_cards():
    response = json.dumps({"stage": "scene_cards", "content": {"scenes": [{"sort_order": 1, "location": "Mountain gate", "goal": "Enter the sect", "conflict": "Guardian blocks entry"}]}})
    provider = _mock_provider(response)
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), params={"stage": "scene_cards"})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["stage"] == "scene_cards"


async def test_architect_build_messages():
    provider = _mock_provider("{}")
    agent = ArchitectAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), params={"stage": "volume_outline"}, pipeline_data={"genre": "xuanhuan"})
    messages = await agent.build_messages(ctx)
    assert len(messages) >= 2
    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    assert "volume_outline" in messages[-1].content


async def test_architect_invalid_json():
    provider = _mock_provider("not json")
    agent = ArchitectAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4(), params={"stage": "chapter_plan"})
    result = await agent.execute(ctx)
    assert result.success is False
