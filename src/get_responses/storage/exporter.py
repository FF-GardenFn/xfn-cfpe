"""Export responses to various formats."""
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from get_responses.config import settings
from get_responses.models import CompletionResponse


class ResponseExporter:
    """Export completion responses to files."""

    def __init__(self, output_dir: Path | None = None):
        """Initialize exporter.

        Args:
            output_dir: Output directory. Uses settings default if None.
        """
        self._output_dir = output_dir or settings.output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export_single(
        self,
        response: CompletionResponse,
        filename: str | None = None,
    ) -> Path:
        """Export a single response to JSON.

        Args:
            response: Response to export
            filename: Optional filename. Auto-generated if None.

        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            query_id = response.query_id or "query"
            prompt_name = response.system_prompt_name or "default"
            filename = f"{query_id}_{prompt_name}_{timestamp}.json"

        filepath = self._output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.model_dump_json(indent=2))

        return filepath

    def export_batch(
        self,
        responses: list[CompletionResponse],
        format: Literal["json", "jsonl"] = "json",
        filename: str | None = None,
    ) -> Path:
        """Export multiple responses.

        Args:
            responses: Responses to export
            format: Output format ('json' or 'jsonl')
            filename: Optional filename. Auto-generated if None.

        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "jsonl" if format == "jsonl" else "json"

        if filename is None:
            filename = f"batch_{timestamp}.{ext}"

        filepath = self._output_dir / filename

        if format == "jsonl":
            with open(filepath, "w", encoding="utf-8") as f:
                for response in responses:
                    f.write(response.model_dump_json() + "\n")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    [r.model_dump() for r in responses],
                    f,
                    indent=2,
                    default=str,
                )

        return filepath

    def export_comparison(
        self,
        baseline: CompletionResponse,
        treatment: CompletionResponse,
        filename: str | None = None,
    ) -> Path:
        """Export a comparison between two responses.

        Args:
            baseline: Baseline response (e.g., no system prompt)
            treatment: Treatment response (e.g., Dialectica)
            filename: Optional filename

        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_id = baseline.query_id or "query"

        if filename is None:
            filename = f"comparison_{query_id}_{timestamp}.json"

        comparison = {
            "query_id": query_id,
            "prompt": baseline.prompt,
            "baseline": baseline.to_summary_dict(),
            "treatment": treatment.to_summary_dict(),
            "comparison": {
                "baseline_tokens": baseline.usage.total_tokens,
                "treatment_tokens": treatment.usage.total_tokens,
                "token_delta": treatment.usage.total_tokens - baseline.usage.total_tokens,
                "baseline_has_thinking": baseline.has_thinking,
                "treatment_has_thinking": treatment.has_thinking,
            },
        }

        filepath = self._output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, default=str)

        return filepath

    def export_summary(
        self,
        responses: list[CompletionResponse],
        filename: str | None = None,
    ) -> Path:
        """Export a summary of all responses.

        Args:
            responses: Responses to summarize
            filename: Optional filename

        Returns:
            Path to exported file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if filename is None:
            filename = f"summary_{timestamp}.json"

        summary = {
            "total_responses": len(responses),
            "timestamp": timestamp,
            "total_tokens": sum(r.usage.total_tokens for r in responses),
            "by_system_prompt": {},
            "responses": [],
        }

        # Group by system prompt
        for response in responses:
            name = response.system_prompt_name
            if name not in summary["by_system_prompt"]:
                summary["by_system_prompt"][name] = {
                    "count": 0,
                    "total_tokens": 0,
                    "avg_latency_ms": 0,
                }
            summary["by_system_prompt"][name]["count"] += 1
            summary["by_system_prompt"][name]["total_tokens"] += response.usage.total_tokens

            summary["responses"].append(response.to_summary_dict())

        # Calculate averages
        for name, data in summary["by_system_prompt"].items():
            matching = [r for r in responses if r.system_prompt_name == name]
            latencies = [r.latency_ms for r in matching if r.latency_ms]
            if latencies:
                data["avg_latency_ms"] = sum(latencies) / len(latencies)

        filepath = self._output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        return filepath


def export_responses(
    responses: list[CompletionResponse],
    output_dir: Path | None = None,
    format: Literal["json", "jsonl"] = "json",
) -> Path:
    """Convenience function to export responses."""
    exporter = ResponseExporter(output_dir)
    return exporter.export_batch(responses, format)
