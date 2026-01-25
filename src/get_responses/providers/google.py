"""Google Gemini provider implementation."""
import time
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse, TokenUsage
from .base import LLMProvider, ProviderError


class GoogleProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: str | None = None):
        """Initialize Google provider.

        Args:
            api_key: Optional API key override. Uses settings if not provided.
        """
        self._api_key = api_key or settings.google_api_key
        if not self._api_key:
            raise ProviderError("google", "API key not configured")
        genai.configure(api_key=self._api_key)

    @property
    def name(self) -> str:
        return "google"

    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash"

    def validate_api_key(self) -> bool:
        return bool(self._api_key)

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute completion request against Google Gemini API."""
        model_name = request.model or self.default_model
        max_tokens = request.max_tokens or settings.max_tokens
        temperature = request.temperature if request.temperature is not None else settings.temperature
        enable_thinking = (
            request.enable_thinking
            if request.enable_thinking is not None
            else settings.enable_thinking
        )
        thinking_budget = request.thinking_budget or settings.thinking_budget

        # Initialize model
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=request.system_prompt if request.system_prompt else None,
        )

        # Build generation config
        gen_config: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        # Gemini 2.0+ supports thinking via thinking_config
        if enable_thinking and self._model_supports_thinking(model_name):
            gen_config["thinking_config"] = {
                "thinking_budget": thinking_budget,
            }

        # Execute request
        start_time = time.perf_counter()
        try:
            response = model.generate_content(
                request.prompt,
                generation_config=GenerationConfig(**gen_config),
            )
        except Exception as e:
            raise ProviderError("google", str(e), e) from e

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content
        answer, thinking = self._extract_content(response)

        # Build token usage from metadata
        usage_metadata = response.usage_metadata if hasattr(response, 'usage_metadata') else None
        input_tokens = getattr(usage_metadata, 'prompt_token_count', 0) if usage_metadata else 0
        output_tokens = getattr(usage_metadata, 'candidates_token_count', 0) if usage_metadata else 0
        thinking_tokens = getattr(usage_metadata, 'thoughts_token_count', None) if usage_metadata else None

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
        )

        # Build raw response dict
        raw_response = {
            "text": answer,
            "thinking": thinking,
            "usage_metadata": {
                "prompt_token_count": input_tokens,
                "candidates_token_count": output_tokens,
                "thoughts_token_count": thinking_tokens,
            } if usage_metadata else None,
        }

        return CompletionResponse(
            answer=answer,
            thinking=thinking if thinking else None,
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            system_prompt_name=request.system_prompt_name,
            query_id=request.query_id,
            provider=self.name,
            model=model_name,
            usage=usage,
            latency_ms=latency_ms,
            raw_response=raw_response,
            tags=request.tags,
        )

    def _model_supports_thinking(self, model: str) -> bool:
        """Check if model supports thinking."""
        thinking_models = [
            "gemini-2.0",
            "gemini-2.5",
            "gemini-3",
            "gemini-1.5-pro",
        ]
        return any(m in model.lower() for m in thinking_models)

    def _extract_content(self, response: Any) -> tuple[str, str]:
        """Extract answer and thinking from response.

        Returns:
            Tuple of (answer_text, thinking_text)
        """
        answer_parts: list[str] = []
        thinking_parts: list[str] = []

        # Gemini returns parts in candidates[0].content.parts
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        thinking_parts.append(part.text if hasattr(part, 'text') else str(part))
                    elif hasattr(part, 'text'):
                        answer_parts.append(part.text)

        # Fallback to simple text extraction
        if not answer_parts and hasattr(response, 'text'):
            answer_parts.append(response.text)

        return "".join(answer_parts), "".join(thinking_parts)
