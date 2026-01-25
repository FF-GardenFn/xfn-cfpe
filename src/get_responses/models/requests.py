"""Request models for LLM completions."""
from typing import Optional

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    """Request for an LLM completion."""

    prompt: str = Field(..., description="User prompt/query")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    system_prompt_name: str = Field(default="default", description="Name/identifier for the system prompt")

    model: Optional[str] = Field(None, description="Model override (uses default if None)")
    max_tokens: Optional[int] = Field(None, description="Max tokens override")
    temperature: Optional[float] = Field(None, description="Temperature override")
    enable_thinking: Optional[bool] = Field(None, description="Enable thinking override")
    thinking_budget: Optional[int] = Field(None, description="Thinking budget override")

    # Metadata
    query_id: Optional[str] = Field(None, description="Unique identifier for this query")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    class Config:
        extra = "forbid"
