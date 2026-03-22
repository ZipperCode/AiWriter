"""Test provider fallback chain functionality."""

import pytest

from app.providers.base import BaseLLMProvider, ChatResponse, ChatChunk
from app.providers.registry import ProviderRegistry
from pydantic import BaseModel
from collections.abc import AsyncIterator


class MockProvider(BaseLLMProvider):
    """Mock provider for testing fallback behavior."""

    def __init__(self, name: str, should_fail: bool = False):
        self._name = name
        self._should_fail = should_fail

    async def chat(
        self, messages, model, temperature=0.7, max_tokens=4096
    ) -> ChatResponse:
        if self._should_fail:
            raise ConnectionError(f"{self._name} failed")
        return ChatResponse(content=f"from-{self._name}", model=model, usage={})

    async def chat_stream(
        self, messages, model, temperature=0.7, max_tokens=4096
    ) -> AsyncIterator[ChatChunk]:
        raise NotImplementedError

    async def structured_output(
        self, messages, model, output_schema, temperature=0.3
    ) -> BaseModel:
        raise NotImplementedError

    async def embedding(self, texts, model="text-embedding-3-large") -> list[list[float]]:
        raise NotImplementedError


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    return ProviderRegistry()


@pytest.mark.asyncio
async def test_set_fallback_chain(registry):
    """Test setting and retrieving fallback chain."""
    # Register providers
    registry.register("provider_a", MockProvider("provider_a"))
    registry.register("provider_b", MockProvider("provider_b"))
    registry.register("provider_c", MockProvider("provider_c"))

    # Set fallback chain
    chain = ["provider_a", "provider_b", "provider_c"]
    registry.set_fallback_chain(chain)

    # Verify it returns a copy, not the original list
    retrieved_chain = registry.get_fallback_chain()
    assert retrieved_chain == chain
    assert retrieved_chain is not chain


@pytest.mark.asyncio
async def test_set_fallback_chain_invalid_provider(registry):
    """Test that set_fallback_chain raises KeyError for non-existent provider."""
    registry.register("provider_a", MockProvider("provider_a"))

    with pytest.raises(KeyError, match="Provider 'provider_b' not registered"):
        registry.set_fallback_chain(["provider_a", "provider_b"])


@pytest.mark.asyncio
async def test_chat_with_fallback_uses_primary(registry):
    """Test that fallback uses primary provider when it works."""
    registry.register("primary", MockProvider("primary", should_fail=False))
    registry.register("secondary", MockProvider("secondary", should_fail=False))
    registry.set_fallback_chain(["primary", "secondary"])

    response = await registry.chat_with_fallback(
        messages=[],
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )

    assert response.content == "from-primary"


@pytest.mark.asyncio
async def test_chat_with_fallback_falls_to_secondary(registry):
    """Test that fallback falls to secondary when primary fails."""
    registry.register("primary", MockProvider("primary", should_fail=True))
    registry.register("secondary", MockProvider("secondary", should_fail=False))
    registry.set_fallback_chain(["primary", "secondary"])

    response = await registry.chat_with_fallback(
        messages=[],
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )

    assert response.content == "from-secondary"


@pytest.mark.asyncio
async def test_chat_with_fallback_all_fail(registry):
    """Test that fallback raises when all providers fail."""
    registry.register("primary", MockProvider("primary", should_fail=True))
    registry.register("secondary", MockProvider("secondary", should_fail=True))
    registry.set_fallback_chain(["primary", "secondary"])

    with pytest.raises(ConnectionError, match="secondary failed"):
        await registry.chat_with_fallback(
            messages=[],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=4096,
        )


@pytest.mark.asyncio
async def test_chat_with_fallback_no_chain_uses_default(registry):
    """Test that fallback uses default provider when no chain is set."""
    registry.register("default_provider", MockProvider("default_provider", should_fail=False))
    registry.set_default("default_provider")

    response = await registry.chat_with_fallback(
        messages=[],
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )

    assert response.content == "from-default_provider"


@pytest.mark.asyncio
async def test_chat_with_fallback_empty_chain(registry):
    """Test that empty fallback chain uses default provider."""
    registry.register("default_provider", MockProvider("default_provider", should_fail=False))
    registry.set_default("default_provider")
    registry.set_fallback_chain([])

    response = await registry.chat_with_fallback(
        messages=[],
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
    )

    assert response.content == "from-default_provider"
