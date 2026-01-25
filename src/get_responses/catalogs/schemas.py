"""Pydantic schemas for experiment configuration."""
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class Provider(str, Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    XAI = "xai"


class ModelConfig(BaseModel):
    """Configuration for a model variant."""
    name: str = Field(..., description="Model nickname: haiku, gpt4o, gemini-flash")
    model_id: str = Field(..., description="Full model ID for API calls")
    provider: Provider = Field(..., description="Provider: anthropic, openai, google, xai")

    # Token limits
    max_output_tokens: int = Field(default=8192, ge=1)
    context_window: int = Field(default=128000, ge=1)

    # Generation config
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)

    # Thinking/reasoning support
    supports_thinking: bool = Field(default=False, description="Extended thinking support")
    thinking_budget: Optional[int] = Field(default=None, ge=1000, le=128000)
    supports_reasoning: bool = Field(default=False, description="o1-style reasoning")

    # Cost tracking (per million tokens)
    cost_per_input_mtok: float = Field(default=0.0, ge=0.0)
    cost_per_output_mtok: float = Field(default=0.0, ge=0.0)
    cost_per_thinking_mtok: Optional[float] = Field(default=None, ge=0.0)

    # Capabilities
    supports_vision: bool = Field(default=False)
    supports_tools: bool = Field(default=True)
    supports_json_mode: bool = Field(default=True)

    class Config:
        extra = "forbid"
        use_enum_values = True


class QueryConfig(BaseModel):
    """Configuration for a test query."""
    id: str = Field(..., description="Query ID: q1, q2, etc.")
    content: str = Field(..., description="Query text")
    category: str = Field(default="general", description="Category: personal, technical, strategic")
    tags: List[str] = Field(default_factory=list)
    expected_mode: Literal["bypass", "light", "full", "ultrathink", "megathink"] = Field(
        default="full",
        description="Expected reasoning mode"
    )
    estimated_tokens: Optional[int] = Field(None, description="For budgeting")
    difficulty: Literal["easy", "medium", "hard", "extreme"] = Field(default="medium")
    reasoning_type: Literal["lookup", "execution", "judgment", "creative"] = Field(default="judgment")

    class Config:
        extra = "forbid"


class SystemPromptConfig(BaseModel):
    """Configuration for a system prompt."""
    name: str = Field(..., description="Prompt identifier: dialectica, baseline")
    version: str = Field(default="1.0", description="Semantic version")
    description: str = Field(default="")
    requires_thinking: bool = Field(default=False)
    recommended_thinking_budget: Optional[int] = Field(default=None)

    class Config:
        extra = "forbid"


class ExperimentConfig(BaseModel):
    """Top-level experiment configuration."""
    name: str = Field(..., description="Experiment ID/name")
    description: str = Field(default="")
    version: str = Field(default="1.0")

    # Which components to use
    models: List[str] = Field(..., description="Model names: [haiku, gpt4o, gemini-flash]")
    system_prompts: List[str] = Field(..., description="System prompt names: [baseline, dialectica]")
    test_queries: List[str] = Field(..., description="Query IDs: [q1, q2, q3]")

    # Configuration options
    export_format: Literal["json", "jsonl"] = Field(default="jsonl")
    export_individual: bool = Field(default=True)
    save_raw_response: bool = Field(default=False)

    # Filtering
    only_mode: Optional[str] = Field(None, description="Filter queries by expected mode")
    only_provider: Optional[Provider] = Field(None, description="Filter to single provider")
    skip_errors: bool = Field(default=False)

    # Metadata
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"
        use_enum_values = True

    @field_validator('models', 'system_prompts', 'test_queries')
    @classmethod
    def ensure_not_empty(cls, v):
        if not v:
            raise ValueError("Must specify at least one item")
        return v
