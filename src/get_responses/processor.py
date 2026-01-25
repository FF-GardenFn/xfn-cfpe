"""Main processing logic for running completions."""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from get_responses.config import settings
from get_responses.models import CompletionRequest, CompletionResponse
from get_responses.prompts import PromptLoader, TestQuery
from get_responses.providers import get_provider, LLMProvider
from get_responses.storage import ResponseExporter

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a batch of queries."""

    responses: list[CompletionResponse] = field(default_factory=list)
    errors: list[tuple[str, Exception]] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.responses)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def total_tokens(self) -> int:
        return sum(r.usage.total_tokens for r in self.responses)


class Processor:
    """Process queries through LLM providers."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        exporter: ResponseExporter | None = None,
        loader: PromptLoader | None = None,
    ):
        """Initialize processor.

        Args:
            provider: LLM provider. Uses default if None.
            exporter: Response exporter. Creates new if None.
            loader: Prompt loader. Creates new if None.
        """
        self._provider = provider or get_provider()
        self._exporter = exporter or ResponseExporter()
        self._loader = loader or PromptLoader()

    def run_single(
        self,
        prompt: str,
        system_prompt: str | None = None,
        system_prompt_name: str = "default",
        query_id: str | None = None,
        tags: list[str] | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """Run a single completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt content
            system_prompt_name: Name for the system prompt
            query_id: Optional query identifier
            tags: Optional tags
            **kwargs: Additional request parameters

        Returns:
            CompletionResponse
        """
        request = CompletionRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            system_prompt_name=system_prompt_name,
            query_id=query_id,
            tags=tags or [],
            **kwargs,
        )
        return self._provider.complete(request)

    def run_comparison(
        self,
        prompt: str,
        baseline_prompt: str | None = None,
        treatment_prompt: str | None = None,
        baseline_name: str = "baseline",
        treatment_name: str = "treatment",
        query_id: str | None = None,
        export: bool = True,
    ) -> tuple[CompletionResponse, CompletionResponse]:
        """Run a comparison between baseline and treatment prompts.

        Args:
            prompt: User prompt
            baseline_prompt: Baseline system prompt (None for no system prompt)
            treatment_prompt: Treatment system prompt
            baseline_name: Name for baseline
            treatment_name: Name for treatment
            query_id: Optional query identifier
            export: Whether to export comparison

        Returns:
            Tuple of (baseline_response, treatment_response)
        """
        baseline = self.run_single(
            prompt=prompt,
            system_prompt=baseline_prompt,
            system_prompt_name=baseline_name,
            query_id=query_id,
        )

        treatment = self.run_single(
            prompt=prompt,
            system_prompt=treatment_prompt,
            system_prompt_name=treatment_name,
            query_id=query_id,
        )

        if export:
            self._exporter.export_comparison(baseline, treatment)

        return baseline, treatment

    def run_batch(
        self,
        queries: list[TestQuery],
        system_prompts: dict[str, str | None],
        on_complete: Callable[[CompletionResponse], None] | None = None,
        export_individual: bool = True,
    ) -> ProcessingResult:
        """Run a batch of queries with multiple system prompts.

        Args:
            queries: List of test queries
            system_prompts: Dict mapping prompt names to content
            on_complete: Optional callback for each completion
            export_individual: Export each response individually

        Returns:
            ProcessingResult with all responses and any errors
        """
        result = ProcessingResult()

        total = len(queries) * len(system_prompts)
        current = 0

        for query in queries:
            for prompt_name, prompt_content in system_prompts.items():
                current += 1
                logger.info(f"Processing {current}/{total}: {query.id} with {prompt_name}")

                try:
                    response = self.run_single(
                        prompt=query.content,
                        system_prompt=prompt_content,
                        system_prompt_name=prompt_name,
                        query_id=query.id,
                        tags=query.tags,
                    )
                    result.responses.append(response)

                    if export_individual:
                        self._exporter.export_single(response)

                    if on_complete:
                        on_complete(response)

                except Exception as e:
                    error_key = f"{query.id}_{prompt_name}"
                    result.errors.append((error_key, e))
                    logger.error(f"Error processing {error_key}: {e}")

        return result

    def run_dialectica_comparison(
        self,
        queries_file: str = "dialectica_tests",
        dialectica_prompt_name: str = "dialectica",
        baseline_prompt: str | None = None,
    ) -> ProcessingResult:
        """Run Dialectica vs baseline comparison.

        Convenience method for the common use case of comparing
        Dialectica system prompt against a baseline.

        Args:
            queries_file: Name of test queries file
            dialectica_prompt_name: Name of Dialectica prompt file
            baseline_prompt: Baseline system prompt content

        Returns:
            ProcessingResult with all responses
        """
        # Load queries
        queries = self._loader.load_test_queries(queries_file)

        # Load Dialectica prompt
        dialectica_prompt = self._loader.load_system_prompt(dialectica_prompt_name)

        # Define system prompts to test
        system_prompts = {
            "baseline": baseline_prompt,
            "dialectica": dialectica_prompt,
        }

        # Run batch
        result = self.run_batch(queries, system_prompts)

        # Export summary
        self._exporter.export_summary(result.responses)

        return result


def run_comparison(
    prompt: str,
    dialectica_prompt: str,
    baseline_prompt: str | None = None,
) -> tuple[CompletionResponse, CompletionResponse]:
    """Convenience function to run a single comparison."""
    processor = Processor()
    return processor.run_comparison(
        prompt=prompt,
        baseline_prompt=baseline_prompt,
        treatment_prompt=dialectica_prompt,
        baseline_name="baseline",
        treatment_name="dialectica",
    )
