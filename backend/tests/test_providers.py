import pytest
from unittest.mock import AsyncMock, patch

from app.providers.base import ChatMessage, ChatResponse
from app.providers.openai_compat import OpenAICompatProvider
from app.providers.registry import ProviderRegistry


def test_provider_registry():
    registry = ProviderRegistry()
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    registry.register("test", provider)
    assert registry.get("test") is provider


def test_provider_registry_unknown():
    registry = ProviderRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent")


def test_provider_registry_list():
    registry = ProviderRegistry()
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    registry.register("p1", provider)
    registry.register("p2", provider)
    assert sorted(registry.list_providers()) == ["p1", "p2"]


async def test_openai_provider_chat_mock():
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    mock_response = ChatResponse(
        content="Hello!",
        model="gpt-4o",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    with patch.object(
        provider, "chat", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await provider.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="gpt-4o",
        )
        assert result.content == "Hello!"
        assert result.model == "gpt-4o"


def test_count_tokens():
    provider = OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="test-key",
    )
    count = provider.count_tokens("Hello, world!", model="gpt-4o")
    assert count > 0
    assert isinstance(count, int)
