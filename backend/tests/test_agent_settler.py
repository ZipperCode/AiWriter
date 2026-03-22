import json
from unittest.mock import AsyncMock
from uuid import uuid4
from app.agents.settler import SettlerAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(return_value=ChatResponse(content=response, model="gemini-flash", usage={}))
    return provider


async def test_settler_execute():
    response = json.dumps({"extracted_entities": [{"name": "叶辰", "type": "character", "confidence": 0.95}], "truth_file_updates": {"current_state": {"last_chapter": 1}}})
    provider = _mock_provider(response)
    agent = SettlerAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "叶辰来到青云宗...", "settlement": {"summary": "叶辰加入青云宗"}})
    result = await agent.execute(ctx)
    assert result.success is True
    assert len(result.data["extracted_entities"]) == 1


async def test_settler_build_messages():
    provider = _mock_provider("{}")
    agent = SettlerAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "Story text here.", "settlement": {"summary": "Things happened"}})
    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert "Story text here" in messages[-1].content


async def test_settler_invalid_response():
    provider = _mock_provider("not json")
    agent = SettlerAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "text"})
    result = await agent.execute(ctx)
    assert result.success is False
