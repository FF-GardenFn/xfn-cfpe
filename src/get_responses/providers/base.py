"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod

from get_responses.models import CompletionRequest, CompletionResponse


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All provider implementations must inherit from this class and implement
    the complete() method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model for this provider."""
        ...

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a completion request.

        Args:
            request: The completion request containing prompt, system prompt, etc.

        Returns:
            CompletionResponse with answer, thinking (if available), and usage stats.

        Raises:
            ProviderError: If the API call fails.
        """
        ...

    def validate_api_key(self) -> bool:
        """Check if API key is configured. Override in subclasses."""
        return True


class ProviderError(Exception):
    """Exception raised when a provider API call fails."""

    def __init__(self, provider: str, message: str, original_error: Exception | None = None):
        self.provider = provider
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{provider}] {message}")
