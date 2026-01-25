"""xAI Grok provider implementation."""
import time
from typing import Any

import openai

from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse, TokenUsage
from .base import LLMProvider, ProviderError


class XAIProvider(LLMProvider):
    """xAI Grok provider.

    Uses OpenAI-compatible API at api.x.ai
    """

    def __init__(self, api_key: str | None = None):
        """Initialize xAI provider.

        Args:
            api_key: Optional API key override. Uses settings if not provided.
        """
        self._api_key = api_key or settings.xai_api_key
        if not self._api_key:
            raise ProviderError("xai", "API key not configured")
        self._client = openai.OpenAI(
            api_key=self._api_key,
            base_url="https://api.x.ai/v1",
        )

    @property
    def name(self) -> str:
        return "xai"

    @property
    def default_model(self) -> str:
        return "grok-2-1212"

    def validate_api_key(self) -> bool:
        return bool(self._api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute completion request against xAI API."""
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
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Execute request
        start_time = time.perf_counter()
        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            raise ProviderError("xai", str(e), e) from e

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content
        answer = response.choices[0].message.content or ""

        # Build token usage
        usage = TokenUsage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            thinking_tokens=None,
        )

        return CompletionResponse(
            answer=answer,
            thinking=None,  # Grok doesn't expose thinking
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            system_prompt_name=request.system_prompt_name,
            query_id=request.query_id,
            provider=self.name,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
            tags=request.tags,
        )
