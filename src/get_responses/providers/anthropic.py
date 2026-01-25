"""Anthropic provider implementation."""
import time
from typing import Any

import anthropic

from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse, TokenUsage
from .base import LLMProvider, ProviderError


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str | None = None):
        """Initialize Anthropic provider.

        Args:
            api_key: Optional API key override. Uses settings if not provided.
        """
        self._api_key = api_key or settings.anthropic_api_key
        if not self._api_key:
            raise ProviderError("anthropic", "API key not configured")
        self._client = anthropic.Anthropic(api_key=self._api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return settings.default_model

    def validate_api_key(self) -> bool:
        return bool(self._api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute completion request against Anthropic API."""
        model = request.model or self.default_model
        max_tokens = request.max_tokens or settings.max_tokens
        temperature = request.temperature if request.temperature is not None else settings.temperature
        enable_thinking = (
            request.enable_thinking
            if request.enable_thinking is not None
            else settings.enable_thinking
        )
        thinking_budget = request.thinking_budget or settings.thinking_budget

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }

        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        # Configure thinking if enabled and model supports it
        if enable_thinking and self._model_supports_thinking(model):
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            # Anthropic requires temperature=1.0 for thinking
            kwargs["temperature"] = 1.0
        else:
            kwargs["temperature"] = temperature

        # Execute request
        start_time = time.perf_counter()
        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APIError as e:
            raise ProviderError("anthropic", str(e), e) from e

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content
        answer, thinking = self._extract_content(response)

        # Build token usage
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            thinking_tokens=getattr(response.usage, "thinking_tokens", None),
        )

        return CompletionResponse(
            answer=answer,
            thinking=thinking if thinking else None,
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            system_prompt_name=request.system_prompt_name,
            query_id=request.query_id,
            provider=self.name,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            raw_response=response.model_dump(),
            tags=request.tags,
        )

    def _model_supports_thinking(self, model: str) -> bool:
        """Check if model supports extended thinking."""
        thinking_models = [
            "claude-3-7",
            "claude-3.7",
            "claude-4",
            "claude-sonnet-4",
            "claude-opus-4",
        ]
        return any(m in model.lower() for m in thinking_models)

    def _extract_content(self, response: Any) -> tuple[str, str]:
        """Extract answer and thinking from response.

        Returns:
            Tuple of (answer_text, thinking_text)
        """
        answer_parts: list[str] = []
        thinking_parts: list[str] = []

        for block in response.content:
            if block.type == "text":
                answer_parts.append(block.text)
            elif block.type == "thinking":
                thinking_parts.append(block.thinking)

        return "".join(answer_parts), "".join(thinking_parts)
