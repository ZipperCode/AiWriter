from app.providers.base import BaseLLMProvider


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseLLMProvider] = {}
        self._default: str | None = None

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


# Global instance
provider_registry = ProviderRegistry()
