"""Response models for LLM completions."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


class TokenUsage(BaseModel):
    """Token usage statistics."""

    input_tokens: int = Field(..., description="Input tokens consumed")
    output_tokens: int = Field(..., description="Output tokens generated")
    thinking_tokens: Optional[int] = Field(None, description="Thinking tokens (if applicable)")

    @computed_field
    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        base = self.input_tokens + self.output_tokens
        if self.thinking_tokens:
            base += self.thinking_tokens
        return base


class CompletionResponse(BaseModel):
    """Response from an LLM completion."""

    # Core content
    answer: str = Field(..., description="Model's response text")
    thinking: Optional[str] = Field(None, description="Chain of thought / thinking content")

    # Request context
    prompt: str = Field(..., description="Original prompt")
    system_prompt: Optional[str] = Field(None, description="System prompt used")
    system_prompt_name: str = Field(default="default", description="System prompt identifier")
    query_id: Optional[str] = Field(None, description="Query identifier")

    # Model info
    provider: str = Field(..., description="Provider name (anthropic, openai, etc.)")
    model: str = Field(..., description="Model used")

    # Usage
    usage: TokenUsage = Field(..., description="Token usage statistics")

    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")

    # Raw response (for debugging)
    raw_response: Optional[dict[str, Any]] = Field(None, description="Raw API response")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags from request")

    @computed_field
    @property
    def has_thinking(self) -> bool:
        """Whether response includes thinking content."""
        return self.thinking is not None and len(self.thinking) > 0

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a summary dict without raw response."""
        data = self.model_dump(exclude={"raw_response"})
        return data
