import json
from unittest.mock import AsyncMock
from uuid import uuid4
from app.agents.auditor import AuditorAgent
from app.agents.reviser import ReviserAgent
from app.providers.base import BaseLLMProvider, ChatResponse
from app.schemas.agent import AgentContext


def _mock_provider(response: str) -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(return_value=ChatResponse(content=response, model="gpt-4o", usage={}))
    return provider


async def test_auditor_execute_pass():
    response = json.dumps({"scores": {"consistency": 8.5, "narrative": 7.0, "style": 9.0}, "pass_rate": 1.0, "has_blocking": False, "issues": [], "recommendation": "pass"})
    provider = _mock_provider(response)
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"draft_id": str(uuid4()), "content": "Good chapter text."})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["recommendation"] == "pass"
    assert result.data["has_blocking"] is False


async def test_auditor_execute_needs_revision():
    response = json.dumps({"scores": {"consistency": 3.0}, "pass_rate": 0.4, "has_blocking": True, "issues": [{"dimension": "consistency", "message": "Character OOC", "severity": "blocking"}], "recommendation": "revise"})
    provider = _mock_provider(response)
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "Bad text."})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["recommendation"] == "revise"


async def test_auditor_build_messages():
    provider = _mock_provider("{}")
    agent = AuditorAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "Text to audit.", "mode": "full"})
    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert "audit" in messages[0].content.lower()


async def test_reviser_execute():
    response = "叶辰踏入了青云宗的大门。"
    provider = _mock_provider(response)
    agent = ReviserAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "Original text.", "mode": "polish", "audit_issues": [{"dimension": "style", "message": "AI traces"}]})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.data["revised_content"] != ""
    assert result.data["word_count"] > 0


async def test_reviser_build_messages():
    provider = _mock_provider("revised")
    agent = ReviserAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4(), chapter_id=uuid4(), pipeline_data={"content": "Original.", "mode": "spot-fix", "audit_issues": [{"message": "fix this"}]})
    messages = await agent.build_messages(ctx)
    assert messages[0].role == "system"
    assert "Original." in messages[-1].content
