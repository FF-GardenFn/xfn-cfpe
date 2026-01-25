"""Provider factory and registry."""
from typing import Callable

from get_responses.config import settings
from .base import LLMProvider, ProviderError
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .google import GoogleProvider
from .xai import XAIProvider


class ProviderRegistry:
    """Registry for LLM providers."""

    _providers: dict[str, Callable[[], LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[[], LLMProvider]) -> None:
        """Register a provider factory.

        Args:
            name: Provider name (e.g., 'anthropic')
            factory: Callable that returns an LLMProvider instance
        """
        cls._providers[name.lower()] = factory

    @classmethod
    def get(cls, name: str) -> LLMProvider:
        """Get a provider instance by name.

        Args:
            name: Provider name

        Returns:
            LLMProvider instance

        Raises:
            ProviderError: If provider is not registered
        """
        name = name.lower()
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ProviderError(
                name,
                f"Provider not registered. Available: {available}",
            )
        return cls._providers[name]()

    @classmethod
    def available(cls) -> list[str]:
        """List available provider names."""
        return list(cls._providers.keys())


# Register built-in providers
ProviderRegistry.register("anthropic", AnthropicProvider)
ProviderRegistry.register("openai", OpenAIProvider)
ProviderRegistry.register("google", GoogleProvider)
ProviderRegistry.register("xai", XAIProvider)


def get_provider(name: str | None = None) -> LLMProvider:
    """Get a provider instance.

    Args:
        name: Provider name. Uses default from settings if None.

    Returns:
        LLMProvider instance
    """
    provider_name = name or settings.default_provider
    return ProviderRegistry.get(provider_name)
