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
            content=response_content,
            model="gpt-4o",
            usage={"input_tokens": 50, "output_tokens": 20},
        )
    )
    return provider


async def test_radar_execute_success():
    response = json.dumps(
        {
            "next_action": "write_chapter",
            "target_chapter_id": str(uuid4()),
            "reasoning": "Chapter 1 is planned and ready to write.",
        }
    )
    provider = _mock_provider(response)
    agent = RadarAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.agent_name == "radar"
    assert result.data["next_action"] == "write_chapter"


async def test_radar_execute_done():
    response = json.dumps(
        {"next_action": "done", "reasoning": "All chapters are finalized."}
    )
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
    assert messages[-1].role == "user"


async def test_radar_handles_invalid_json():
    provider = _mock_provider("not valid json at all")
    agent = RadarAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is False
