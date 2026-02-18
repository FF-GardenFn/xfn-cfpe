#!/usr/bin/env python3
"""
Rescore existing experiment results with the intent-aware fix.

This script recomputes metrics from the raw results JSON, applying the fix
where refusals that mention dangerous patterns are no longer counted as violations.

Usage:
    python rescore_results.py [--input PATH] [--output PATH]

Example:
    python rescore_results.py --input results/experiment_v4_results.json
"""

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from config import CONDITIONS
from analysis.metrics import (
    rescore_with_intent_fix,
    display_corrected_comparison,
    analyze_results,
    display_results,
    summarize_key_findings,
)

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Rescore experiment results with intent fix")
    parser.add_argument(
        "--input",
        type=str,
        default="results/experiment_v4_results.json",
        help="Input results JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for corrected results (optional)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Error: {input_path} not found[/red]")
        return

    # Load results
    with open(input_path) as f:
        data = json.load(f)

    raw_results = data.get("raw_results", [])
    original_metrics = data.get("metrics", {})

    console.print(f"[bold]Rescoring {len(raw_results)} results from {input_path}[/bold]\n")

    # Compute corrected metrics
    corrected_metrics = rescore_with_intent_fix(raw_results)

    # Show comparison
    display_corrected_comparison(original_metrics, corrected_metrics)

    # Show detailed corrected results
    console.print("\n[bold cyan]CORRECTED DETAILED RESULTS:[/bold cyan]")

    table = Table()
    table.add_column("Model", style="bold")
    table.add_column("baseline", justify="right")
    table.add_column("cai", justify="right")
    table.add_column("kernel_only", justify="right")
    table.add_column("cai_kernel", justify="right", style="green")

    for model in corrected_metrics:
        model_short = "OPUS" if "opus" in model.lower() else "SONNET" if "sonnet" in model.lower() else model
        row = [model_short]
        for condition in CONDITIONS:
            rate = corrected_metrics.get(model, {}).get(condition, {}).get('residual_violation_rate', 0)
            row.append(f"{rate:.1%}")
        table.add_row(*row)

    console.print(table)

    # Interpretation
    console.print("\n[bold yellow]INTERPRETATION:[/bold yellow]")

    for model in corrected_metrics:
        model_short = "OPUS" if "opus" in model.lower() else "SONNET" if "sonnet" in model.lower() else model
        m = corrected_metrics[model]

        baseline = m.get('baseline', {}).get('residual_violation_rate', 0)
        cai = m.get('cai', {}).get('residual_violation_rate', 0)
        kernel = m.get('kernel_only', {}).get('residual_violation_rate', 0)
        combined = m.get('cai_kernel', {}).get('residual_violation_rate', 0)

        cai_effect = baseline - cai
        kernel_effect = baseline - kernel
        combined_effect = baseline - combined

        console.print(f"\n  [bold]{model_short}:[/bold]")
        console.print(f"    CAI effect:      {baseline:.1%} → {cai:.1%} ({cai_effect:+.1%})")
        console.print(f"    Kernel effect:   {baseline:.1%} → {kernel:.1%} ({kernel_effect:+.1%})")
        console.print(f"    Combined effect: {baseline:.1%} → {combined:.1%} ({combined_effect:+.1%})")

        # Which is better?
        if cai < kernel:
            console.print(f"    [cyan]CAI > Kernel for {model_short}[/cyan]")
        elif kernel < cai:
            console.print(f"    [cyan]Kernel > CAI for {model_short}[/cyan]")
        else:
            console.print(f"    [cyan]CAI = Kernel for {model_short}[/cyan]")

    # Save corrected if requested
    if args.output:
        output_path = Path(args.output)
        output_data = {
            **data,
            "metrics_corrected": corrected_metrics,
            "correction_applied": "intent_aware_text_violation_fix",
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        console.print(f"\n[green]Saved corrected results to {output_path}[/green]")


if __name__ == "__main__":
    main()
