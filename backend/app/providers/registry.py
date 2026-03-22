from app.providers.base import BaseLLMProvider, ChatResponse
from app.logging import get_logger

logger = get_logger(__name__)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseLLMProvider] = {}
        self._default: str | None = None
        self._fallback_chain: list[str] = []

    def register(self, name: str, provider: BaseLLMProvider, is_default: bool = False) -> None:
        self._providers[name] = provider
        if is_default:
            self._default = name

    def get(self, name: str) -> BaseLLMProvider:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        return self._providers[name]

    def get_default(self) -> BaseLLMProvider:
        if self._default is None:
            raise RuntimeError("No default provider registered")
        return self._providers[self._default]

    def set_default(self, name: str) -> None:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        self._default = name

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def set_fallback_chain(self, chain: list[str]) -> None:
        """Set the fallback chain for automatic provider failover.

        Args:
            chain: List of provider names to try in order

        Raises:
            KeyError: If any provider name in the chain is not registered
        """
        # Validate all providers exist
        for name in chain:
            if name not in self._providers:
                raise KeyError(f"Provider '{name}' not registered")
        self._fallback_chain = chain
        logger.info("fallback_chain_set", chain=chain)

    def get_fallback_chain(self) -> list[str]:
        """Get the current fallback chain.

        Returns:
            A copy of the fallback chain list
        """
        return list(self._fallback_chain)

    async def chat_with_fallback(
        self,
        messages,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """Execute chat request with automatic fallback to next provider on failure.

        If a fallback chain is set, tries providers in order. If all fail, raises the last error.
        If no chain is set, uses the default provider.

        Args:
            messages: Chat messages
            model: Model name
            temperature: Temperature for generation
            max_tokens: Max tokens for generation

        Returns:
            ChatResponse from the first successful provider

        Raises:
            RuntimeError: If no fallback chain set and no default provider
            Exception: Last error from all providers if all fail
        """
        # Use fallback chain if set, otherwise use default
        providers_to_try = self._fallback_chain if self._fallback_chain else [self._default]

        if not providers_to_try or providers_to_try[0] is None:
            raise RuntimeError("No fallback chain set and no default provider registered")

        last_error = None
        for provider_name in providers_to_try:
            try:
                provider = self.get(provider_name)
                logger.debug(
                    "fallback_trying_provider",
                    provider=provider_name,
                    model=model,
                )
                response = await provider.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                logger.info(
                    "fallback_provider_success",
                    provider=provider_name,
                    model=model,
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    "fallback_provider_failed",
                    provider=provider_name,
                    error=str(e),
                )
                continue

        # All providers failed, raise the last error
        if last_error:
            raise last_error
        raise RuntimeError("All fallback providers failed")


# Global instance
provider_registry = ProviderRegistry()
