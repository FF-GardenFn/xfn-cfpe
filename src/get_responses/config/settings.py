"""Configuration management using pydantic-settings.

Supports environment variables and .env files for configuration.
All settings can be overridden via environment variables with the same name.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    google_api_key: str = Field(default="", description="Google AI API key")
    xai_api_key: str = Field(default="", description="xAI API key")

    # Model Configuration
    default_provider: str = Field(default="anthropic", description="Default LLM provider")
    default_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model to use",
    )

    # Generation Parameters
    max_tokens: int = Field(default=8192, ge=1, le=32768, description="Maximum tokens")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Temperature")
    enable_thinking: bool = Field(default=True, description="Enable extended thinking")
    thinking_budget: int = Field(default=10000, ge=1000, le=20000, description="Thinking budget")

    # Paths (relative to project root)
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent,
        description="Project root directory",
    )

    @property
    def system_prompts_dir(self) -> Path:
        return self.project_root / "system_prompts"

    @property
    def test_queries_dir(self) -> Path:
        return self.project_root / "test_queries"

    @property
    def output_dir(self) -> Path:
        return self.project_root / "data"

    @field_validator("temperature")
    @classmethod
    def validate_temperature_for_thinking(cls, v: float) -> float:
        """Note: When thinking is enabled, Anthropic requires temperature=1.0."""
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton instance
settings = get_settings()
