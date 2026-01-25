"""Prompt loading utilities."""
import re
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, Field

from get_responses.config import settings


class TestQuery(BaseModel):
    """A test query with metadata."""

    id: str = Field(..., description="Query identifier")
    content: str = Field(..., description="Query content")
    tags: list[str] = Field(default_factory=list, description="Query tags/categories")
    expected_mode: str = Field(default="dialectic", description="Expected mode: dialectic or bypass")


class PromptLoader:
    """Load system prompts and test queries from files."""

    def __init__(
        self,
        system_prompts_dir: Path | None = None,
        test_queries_dir: Path | None = None,
    ):
        """Initialize loader with optional custom directories."""
        self._system_prompts_dir = system_prompts_dir or settings.system_prompts_dir
        self._test_queries_dir = test_queries_dir or settings.test_queries_dir

    def load_system_prompt(self, name: str) -> str:
        """Load a system prompt by name.

        Args:
            name: Prompt name (without .md extension)

        Returns:
            Prompt content as string

        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        # Try multiple extensions
        for ext in [".md", ".txt", ""]:
            path = self._system_prompts_dir / f"{name}{ext}"
            if path.exists():
                return path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"System prompt '{name}' not found in {self._system_prompts_dir}"
        )

    def list_system_prompts(self) -> list[str]:
        """List available system prompts."""
        if not self._system_prompts_dir.exists():
            return []
        return [
            p.stem for p in self._system_prompts_dir.glob("*.md")
        ]

    def load_test_queries(self, name: str) -> list[TestQuery]:
        """Load test queries from a file.

        Supports numbered format:
        1. [Tag] Query content
        2. [Tag] Another query

        Args:
            name: File name (without extension)

        Returns:
            List of TestQuery objects
        """
        # Try multiple extensions
        for ext in [".md", ".txt", ""]:
            path = self._test_queries_dir / f"{name}{ext}"
            if path.exists():
                return self._parse_queries(path.read_text(encoding="utf-8"))

        raise FileNotFoundError(
            f"Test queries '{name}' not found in {self._test_queries_dir}"
        )

    def _parse_queries(self, content: str) -> list[TestQuery]:
        """Parse numbered queries from content."""
        queries: list[TestQuery] = []

        # Pattern: number. [optional tag] content
        pattern = r"(?m)^(\d+)\.\s*(?:\[([^\]]+)\])?\s*(.+?)(?=^\d+\.|\Z)"

        for match in re.finditer(pattern, content, re.DOTALL):
            query_num = match.group(1)
            tag = match.group(2)
            content_text = match.group(3).strip()

            tags = [tag.strip()] if tag else []

            # Determine expected mode based on tag or section
            expected_mode = "bypass" if any(
                t.lower() in ["formatting", "syntax", "trivia", "language", "coding"]
                for t in tags
            ) else "dialectic"

            queries.append(TestQuery(
                id=f"q{query_num}",
                content=content_text,
                tags=tags,
                expected_mode=expected_mode,
            ))

        return queries

    def iter_test_queries(self, name: str) -> Iterator[TestQuery]:
        """Iterate over test queries lazily."""
        yield from self.load_test_queries(name)


def load_system_prompt(name: str) -> str:
    """Convenience function to load a system prompt."""
    return PromptLoader().load_system_prompt(name)


def load_test_queries(name: str) -> list[TestQuery]:
    """Convenience function to load test queries."""
    return PromptLoader().load_test_queries(name)
