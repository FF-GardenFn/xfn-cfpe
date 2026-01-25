"""LLM Response Collection Tool.

A modular, extensible framework for collecting and comparing
LLM responses across different system prompts and providers.
"""
from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse, TokenUsage
from get_responses.processor import Processor, ProcessingResult, run_comparison
from get_responses.providers import get_provider, LLMProvider, AnthropicProvider

__version__ = "0.1.0"

__all__ = [
    # Config
    "settings",
    # Models
    "CompletionRequest",
    "CompletionResponse",
    "TokenUsage",
    # Processing
    "Processor",
    "ProcessingResult",
    "run_comparison",
    # Providers
    "get_provider",
    "LLMProvider",
    "AnthropicProvider",
]
