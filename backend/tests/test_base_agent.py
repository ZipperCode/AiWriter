import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.agents.base import BaseAgent
from app.providers.base import BaseLLMProvider, ChatMessage, ChatResponse
from app.schemas.agent import AgentContext, AgentResult, ValidationIssue


class StubAgent(BaseAgent):
    """A concrete agent for testing the base class."""
    name = "stub"
    description = "Test stub agent"
    temperature = 0.5

    async def build_messages(self, context: AgentContext) -> list[ChatMessage]:
        return [
            ChatMessage(role="system", content="You are a stub."),
            ChatMessage(role="user", content="Do something."),
        ]

    async def _call_llm(self, messages: list[ChatMessage], context: AgentContext):
        resp = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        return {"content": resp.content}


class FailOnceAgent(BaseAgent):
    """Agent that fails on first attempt, succeeds on second."""
    name = "fail_once"
    description = "Fails once then succeeds"
    max_retries = 3

    def __init__(self, provider, model="gpt-4o"):
        super().__init__(provider, model)
        self.attempt_count = 0

    async def build_messages(self, context):
        return [ChatMessage(role="user", content="test")]

    async def _call_llm(self, messages, context):
        self.attempt_count += 1
        if self.attempt_count == 1:
            raise ValueError("Simulated LLM failure")
        return {"result": "ok"}

    async def on_retry(self, error, attempt):
        pass  # no wait in tests


class ValidatingAgent(BaseAgent):
    """Agent that always fails validation."""
    name = "validating"
    description = "Tests validation"

    async def build_messages(self, context):
        return [ChatMessage(role="user", content="test")]

    async def _call_llm(self, messages, context):
        return {"content": ""}

    async def validate_output(self, result):
        return [ValidationIssue(field="content", message="empty", severity="error")]

    async def on_retry(self, error, attempt):
        pass


def _make_mock_provider() -> BaseLLMProvider:
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.chat = AsyncMock(
        return_value=ChatResponse(content="Hello!", model="gpt-4o", usage={"input_tokens": 10, "output_tokens": 5})
    )
    return provider


async def test_base_agent_execute_success():
    provider = _make_mock_provider()
    agent = StubAgent(provider=provider, model="gpt-4o")
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.agent_name == "stub"
    assert result.data["content"] == "Hello!"
    assert result.duration_ms >= 0
    assert result.error is None


async def test_base_agent_retry_on_failure():
    provider = _make_mock_provider()
    agent = FailOnceAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is True
    assert agent.attempt_count == 2


async def test_base_agent_all_retries_exhausted():
    provider = _make_mock_provider()
    agent = FailOnceAgent(provider=provider)
    agent.max_retries = 1
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is False
    assert "Simulated LLM failure" in result.error


async def test_base_agent_validation_triggers_retry():
    provider = _make_mock_provider()
    agent = ValidatingAgent(provider=provider)
    agent.max_retries = 2
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    # Last attempt returns success even with validation issues
    assert result.success is True
    assert result.agent_name == "validating"


async def test_base_agent_attributes():
    provider = _make_mock_provider()
    agent = StubAgent(provider=provider, model="claude-3")
    assert agent.name == "stub"
    assert agent.model == "claude-3"
    assert agent.temperature == 0.5
    assert agent.max_retries == 3
    assert agent.timeout_seconds == 120


async def test_base_agent_timeout():
    """Agent should fail when _call_llm exceeds timeout_seconds."""
    import asyncio

    class SlowAgent(BaseAgent):
        name = "slow"
        timeout_seconds = 1
        max_retries = 1

        async def build_messages(self, context):
            return [ChatMessage(role="user", content="test")]

        async def _call_llm(self, messages, context):
            await asyncio.sleep(5)
            return {"result": "ok"}

    provider = _make_mock_provider()
    agent = SlowAgent(provider=provider)
    ctx = AgentContext(project_id=uuid4())
    result = await agent.execute(ctx)
    assert result.success is False
    assert "timed out" in result.error.lower()
