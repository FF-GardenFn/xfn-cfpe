"""OpenAI provider implementation."""
import time
from typing import Any

import openai

from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse, TokenUsage
from .base import LLMProvider, ProviderError


class OpenAIProvider(LLMProvider):
    """OpenAI GPT/o-series provider."""

    def __init__(self, api_key: str | None = None):
        """Initialize OpenAI provider.

        Args:
            api_key: Optional API key override. Uses settings if not provided.
        """
        self._api_key = api_key or settings.openai_api_key
        if not self._api_key:
            raise ProviderError("openai", "API key not configured")
        self._client = openai.OpenAI(api_key=self._api_key)

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    def validate_api_key(self) -> bool:
        return bool(self._api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute completion request against OpenAI API."""
        model = request.model or self.default_model
        max_tokens = request.max_tokens or settings.max_tokens
        temperature = request.temperature if request.temperature is not None else settings.temperature

        # Build messages
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # o-series models (o1, o3) use max_completion_tokens instead of max_tokens
        # and don't support temperature
        if self._is_reasoning_model(model):
            kwargs["max_completion_tokens"] = max_tokens
            # o-series doesn't support system messages in the same way
            # Move system content to user message if present
            if request.system_prompt and len(messages) > 1:
                combined = f"{request.system_prompt}\n\n---\n\n{request.prompt}"
                kwargs["messages"] = [{"role": "user", "content": combined}]
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature

        # Execute request
        start_time = time.perf_counter()
        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            raise ProviderError("openai", str(e), e) from e

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content
        answer = response.choices[0].message.content or ""

        # o-series includes reasoning in a separate field (if available)
        thinking = None
        if hasattr(response.choices[0].message, 'reasoning_content'):
            thinking = response.choices[0].message.reasoning_content

        # Build token usage
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            thinking_tokens=getattr(response.usage, 'reasoning_tokens', None),
        )

        return CompletionResponse(
            answer=answer,
            thinking=thinking,
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

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is an o-series reasoning model."""
        reasoning_prefixes = ["o1", "o3"]
        model_lower = model.lower()
        return any(model_lower.startswith(p) or f"-{p}" in model_lower for p in reasoning_prefixes)
