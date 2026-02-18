#!/usr/bin/env python3
"""
Constitutional Kernel Experiment v4 - Main Entry Point

Usage:
    python run_experiment.py [--models MODEL1,MODEL2] [--trials N] [--output PATH]

Example:
    python run_experiment.py --models claude-4-5-sonnet-20260115 --trials 3
"""

import argparse
import json
import datetime
import statistics
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from config import EXPERIMENT_MODELS, RESULTS_DIR, ENV_FILE, N_TRIALS, CONDITIONS
from models import TrialResult
from kernel import ConstitutionalKernel
from classifier import IntentClassifier
from experiment import ExperimentRunner, TASKS
from experiment.task_suite import get_task_stats
from analysis import analyze_results, display_results
from analysis.metrics import summarize_key_findings, analyze_violation_taxonomy, display_violation_taxonomy


console = Console()


def run_with_trials(
    runner: ExperimentRunner,
    kernel: ConstitutionalKernel,
    models: list[str],
    n_trials: int,
) -> list[TrialResult]:
    """Run experiment with multiple trials per task."""
    all_results: list[TrialResult] = []

    total_calls = len(models) * len(TASKS) * len(CONDITIONS) * n_trials

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:

        task_progress = progress.add_task("Running experiment...", total=total_calls)

        for model in models:
            # Extract readable model name
            if "sonnet" in model.lower():
                model_short = "SONNET-4.5"
            elif "opus" in model.lower():
                model_short = "OPUS-4.5"
            elif "haiku" in model.lower():
                model_short = "HAIKU-4.5"
            else:
                model_short = model.split("-")[0].upper()

            console.print(f"\n[bold yellow]▶ {model_short}[/bold yellow]")

            for task in TASKS:
                # Collect results across trials for this task
                task_results = {cond: [] for cond in CONDITIONS}

                console.print(f"  {task.id[:20]:20s} ", end="")

                for trial in range(n_trials):
                    for condition in CONDITIONS:
                        result = runner.run_trial(task, condition, model)
                        all_results.append(result)
                        task_results[condition].append(result)
                        progress.update(task_progress, advance=1)

                # Show summary for this task (across trials)
                for condition in CONDITIONS:
                    results = task_results[condition]
                    successes = sum(1 for r in results if r.task_success)
                    violations = sum(1 for r in results if r.residual_violation)

                    if violations == n_trials:
                        console.print("[red]✗[/red]", end="")
                    elif violations > 0:
                        console.print("[yellow]~[/yellow]", end="")  # Mixed
                    elif successes == n_trials:
                        console.print("[green]✓[/green]", end="")
                    else:
                        console.print("[cyan]○[/cyan]", end="")

                console.print(f" ({n_trials}x)")

            kernel.reset()

    return all_results


def compute_variance_stats(results: list[TrialResult]) -> dict:
    """Compute variance statistics across trials."""
    stats = {}

    models = set(r.model for r in results)

    for model in models:
        stats[model] = {}
        for condition in CONDITIONS:
            cond_results = [r for r in results if r.model == model and r.condition == condition]

            # Group by task
            task_ids = set(r.task_id for r in cond_results)

            success_rates = []
            violation_rates = []

            for task_id in task_ids:
                task_results = [r for r in cond_results if r.task_id == task_id]
                if task_results:
                    success_rates.append(sum(r.task_success for r in task_results) / len(task_results))
                    violation_rates.append(sum(r.residual_violation for r in task_results) / len(task_results))

            stats[model][condition] = {
                "success_mean": statistics.mean(success_rates) if success_rates else 0,
                "success_stdev": statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
                "violation_mean": statistics.mean(violation_rates) if violation_rates else 0,
                "violation_stdev": statistics.stdev(violation_rates) if len(violation_rates) > 1 else 0,
            }

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Constitutional Kernel Experiment v4"
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(EXPERIMENT_MODELS),
        help="Comma-separated model IDs",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=N_TRIALS,
        help=f"Number of trials per task (default: {N_TRIALS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_DIR / "experiment_v4_results.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration without running",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")]
    n_trials = args.trials

    # Load environment
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    # Task stats
    task_stats = get_task_stats()

    console.print("[bold]Constitutional Kernel Experiment v4.0[/bold]")
    console.print(f"[bold]Sophisticated Adversarial Prompts[/bold]\n")
    console.print(f"Models: {models}")
    console.print(f"Tasks: {task_stats['total']} ({task_stats['benign']} benign, {task_stats['boundary']} boundary, {task_stats['adversarial']} adversarial)")
    console.print(f"Trials per task: {n_trials}")
    console.print(f"Conditions: {', '.join(CONDITIONS)}")

    total_main = len(models) * task_stats['total'] * len(CONDITIONS) * n_trials
    console.print(f"Total API calls: ~{total_main} main + classifier calls")
    console.print(f"\nAdversarial techniques: {', '.join(task_stats['adversarial_techniques'])}\n")

    if args.dry_run:
        console.print("[yellow]Dry run - exiting[/yellow]")
        return

    # Initialize
    client = anthropic.Anthropic()
    kernel = ConstitutionalKernel()
    classifier = IntentClassifier(client)
    runner = ExperimentRunner(client, kernel, classifier)

    # Run with multiple trials
    all_results = run_with_trials(runner, kernel, models, n_trials)

    # Analyze
    console.print("\n")
    metrics = analyze_results(all_results)
    variance_stats = compute_variance_stats(all_results)
    taxonomy = analyze_violation_taxonomy(all_results)

    display_results(metrics)
    summarize_key_findings(metrics)
    display_violation_taxonomy(taxonomy)

    # Show variance info
    console.print("\n[bold cyan]VARIANCE ANALYSIS:[/bold cyan]")
    for model in variance_stats:
        model_short = "SONNET" if "sonnet" in model.lower() else "OPUS" if "opus" in model.lower() else model
        console.print(f"\n  [bold]{model_short}:[/bold]")
        for condition in CONDITIONS:
            s = variance_stats[model].get(condition, {})
            console.print(f"    {condition:12s}: success={s.get('success_mean', 0):.0%}±{s.get('success_stdev', 0):.0%}, violations={s.get('violation_mean', 0):.0%}±{s.get('violation_stdev', 0):.0%}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "4.0.0",  # 4-condition grid
        "models": models,
        "n_trials": n_trials,
        "task_stats": task_stats,
        "conditions": CONDITIONS,
        "metrics": metrics,
        "variance_stats": variance_stats,
        "violation_taxonomy": taxonomy,
        "raw_results": [r.to_dict() for r in all_results],
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    console.print(f"\n[green]✓ Results saved to {output_path}[/green]")


if __name__ == "__main__":
    main()
