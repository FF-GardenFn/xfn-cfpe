"""
ti — Training Insights CLI

Autonomous training experiment platform with multi-dimensional checkpoint evaluation.

Commands:
    ti run       Start the autonomous experiment loop
    ti analyze   Extract insights from experiment history
    ti status    Show dashboard: experiments, best BPB, best reward, Pareto frontier
    ti report    Generate full markdown report for the latest (or specified) experiment

Usage:
    ti run --hypothesis "increase embedding_lr 0.6 → 0.8"
    ti run --loop --max-experiments 50
    ti analyze
    ti analyze --json-dir runs/ --output insights.md
    ti status
    ti report --step 5
    ti report --latest
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ti")


# ---------------------------------------------------------------------------
# Command: status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    """Print a live dashboard of experiment history."""
    results_file = Path(args.results_file)
    json_dir = Path(args.json_dir) if args.json_dir else results_file.parent / "runs"

    try:
        from training_insights.evaluation.insights import InsightEngine
    except ImportError as e:
        print(f"[ti] Import error: {e}", file=sys.stderr)
        return 1

    engine = InsightEngine(results_file=results_file, json_dir=json_dir)
    report = engine.analyze()

    if report.n_total == 0:
        print("[ti status] No experiments found. Run `ti run` to start.")
        return 0

    # Header banner
    keep_pct = 100 * report.n_kept / max(1, report.n_total)
    print("\n" + "═" * 60)
    print("  Training Insights — Experiment Dashboard")
    print("═" * 60)
    print(f"  Experiments   : {report.n_total} total  "
          f"({report.n_kept} kept {keep_pct:.0f}%  |  "
          f"{report.n_discarded} discarded  |  {report.n_crashed} crashed)")

    if report.best_bpb < float("inf"):
        print(f"  Best val_bpb  : {report.best_bpb:.6f}")
        print(f"  Best reward   : R={report.best_reward:+.4f}")
        print(f"  Best hyp.     : {report.best_hypothesis}")

    # Family attribution table
    if report.family_stats:
        print("\n  Hyperparameter Family Attribution")
        print("  " + "─" * 56)
        icons = {"promising": "✓", "dead_end": "✗", "neutral": "~", "insufficient_data": "?"}
        for fs in sorted(report.family_stats, key=lambda x: x.mean_reward_delta, reverse=True):
            icon = icons.get(fs.verdict, "?")
            bar_len = int(max(0, min(20, (fs.mean_reward_delta + 0.05) * 100)))
            bar = "█" * bar_len
            print(f"  {icon} {fs.family:<20} n={fs.n_experiments:<3} "
                  f"kept={fs.n_kept:<3} ΔR={fs.mean_reward_delta:+.4f}  {bar}")

    # Safety drift
    sd = report.safety_drift
    print(f"\n  Safety Drift  : {sd.drift:+.4f}  "
          f"(baseline={sd.baseline_safety:.4f} → current={sd.current_safety:.4f})")
    if sd.inversion_detected:
        print(f"  ⚠ CAI INVERSION: capability improved while safety worsened "
              f"(magnitude={sd.inversion_magnitude:+.4f})")

    # Pareto frontier
    pareto = [p for p in report.pareto_frontier if p.is_pareto_optimal]
    if pareto:
        print(f"\n  Pareto Frontier ({len(pareto)} optimal experiments)")
        print("  " + "─" * 56)
        for p in sorted(pareto, key=lambda x: x.quality, reverse=True):
            print(f"    #{p.step:<3} Q={p.quality:.3f} C={p.cost:.3f} "
                  f"R={p.reward:+.4f} BPB={p.val_bpb:.6f}  {p.hypothesis[:40]}")

    print("═" * 60 + "\n")
    return 0


# ---------------------------------------------------------------------------
# Command: analyze
# ---------------------------------------------------------------------------

def cmd_analyze(args: argparse.Namespace) -> int:
    """Extract and print full insight analysis."""
    results_file = Path(args.results_file)
    json_dir = Path(args.json_dir) if args.json_dir else results_file.parent / "runs"

    try:
        from training_insights.evaluation.insights import InsightEngine
    except ImportError as e:
        print(f"[ti] Import error: {e}", file=sys.stderr)
        return 1

    engine = InsightEngine(results_file=results_file, json_dir=json_dir)
    report = engine.analyze()

    if report.n_total == 0:
        print("[ti analyze] No experiments found. Run `ti run` to start.")
        return 0

    output = report.summary() + "\n\n" + report.next_hypothesis_context()

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"[ti analyze] Insights written to {out_path}")
    else:
        print(output)

    return 0


# ---------------------------------------------------------------------------
# Command: run
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Run one experiment, or loop autonomously."""
    results_file = Path(args.results_file)
    json_dir = Path(args.json_dir) if args.json_dir else results_file.parent / "runs"

    try:
        from training_insights.evaluation.runner import ExperimentRunner
        from training_insights.evaluation.insights import InsightEngine
    except ImportError as e:
        print(f"[ti] Import error: {e}", file=sys.stderr)
        return 1

    # Seed baseline from the SAME experiment (best composite R among kept runs).
    # Using best_bpb and best_reward from different experiments would be
    # logically inconsistent — the evaluator assumes both baselines come from
    # the same checkpoint.
    engine = InsightEngine(results_file=results_file, json_dir=json_dir)
    history = engine.analyze()
    baseline_bpb: float | None = None
    baseline_composite: float | None = None
    kept = [r for r in history.records if r.keep and r.val_bpb > 0]
    if kept:
        best = max(kept, key=lambda r: r.composite_reward)
        baseline_bpb = best.val_bpb
        baseline_composite = best.composite_reward

    runner = ExperimentRunner(
        results_file=results_file,
        json_dir=json_dir,
        baseline_bpb=baseline_bpb,
        baseline_composite=baseline_composite,
        alpha=args.alpha,
        beta=args.beta,
        gamma=args.gamma,
        timeout_sec=args.timeout,
        auto_git=not args.no_git,
    )

    if args.loop:
        # Autonomous loop
        max_exp = args.max_experiments
        print(f"[ti run] Starting autonomous loop (max={max_exp or '∞'} experiments)")
        print("[ti run] Press Ctrl-C to stop.\n")
        count = 0
        try:
            while max_exp is None or count < max_exp:
                # Re-analyze history to get current insight context for hypothesis
                current_insights = InsightEngine(
                    results_file=results_file, json_dir=json_dir
                ).analyze()
                context = current_insights.next_hypothesis_context()

                # In loop mode without a hypothesis, print context and pause for input
                if sys.stdin.isatty():
                    print("\n" + context)
                    hypothesis = input("[ti run] Hypothesis for experiment "
                                      f"#{runner._experiment_count + 1}: ").strip()
                    if not hypothesis:
                        print("[ti run] Empty hypothesis — stopping loop.")
                        break
                else:
                    # Non-interactive: use insight-driven placeholder
                    fam = (current_insights.promising_families or ["baseline"])[0]
                    hypothesis = f"auto: explore {fam} family"

                runner.run_experiment(
                    hypothesis=hypothesis,
                    train_cmd=args.train_cmd,
                    cwd=args.cwd,
                )
                count += 1
        except KeyboardInterrupt:
            print("\n[ti run] Loop interrupted.")
        return 0

    # Single experiment
    hypothesis = args.hypothesis or "baseline (no changes)"
    runner.run_experiment(
        hypothesis=hypothesis,
        train_cmd=args.train_cmd,
        cwd=args.cwd,
    )
    return 0


# ---------------------------------------------------------------------------
# Command: report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    """Generate a unified markdown report for a specific experiment."""
    results_file = Path(args.results_file)
    json_dir = Path(args.json_dir) if args.json_dir else results_file.parent / "runs"

    try:
        from training_insights.evaluation.insights import InsightEngine
        from training_insights.evaluation.report import ExperimentReportWriter
        from training_insights.evaluation.parser import parse_training_output
    except ImportError as e:
        print(f"[ti] Import error: {e}", file=sys.stderr)
        return 1

    engine = InsightEngine(results_file=results_file, json_dir=json_dir)
    history = engine.analyze()

    if history.n_total == 0:
        print("[ti report] No experiments found.")
        return 1

    # Find target step
    if args.latest:
        target_step = max(r.step for r in history.records)
    elif args.step is not None:
        target_step = args.step
    else:
        target_step = max(r.step for r in history.records)

    # Load the JSON for that step
    json_path = None
    for fp in json_dir.glob(f"experiment_{target_step}_*.json"):
        json_path = fp
        break

    if not json_path or not json_path.exists():
        print(f"[ti report] No JSON found for experiment #{target_step} in {json_dir}")
        return 1

    import json
    data = json.loads(json_path.read_text())

    # Reconstruct CheckpointReport from JSON
    from training_insights.evaluation.checkpoint_eval import (
        CheckpointReport, TrainingMetrics, ProcessRewards, SafetyProfile
    )
    from datetime import datetime

    tr = data.get("training", {})
    metrics = TrainingMetrics(
        val_bpb=tr.get("val_bpb", 0.0),
        core_score=tr.get("core_score", 0.0),
        mfu_pct=tr.get("mfu_pct", 0.0),
        peak_vram_gb=tr.get("peak_vram_gb", 0.0),
        wall_time_sec=tr.get("wall_time_sec", 0.0),
        total_tokens=tr.get("total_tokens", 0),
    )
    pr_data = data.get("process_rewards", {})
    process = ProcessRewards(
        resonance=pr_data.get("resonance", 0.0),
        structure=pr_data.get("structure", 0.0),
        goldilocks=pr_data.get("goldilocks", True),
    )
    s_data = data.get("safety", {})
    safety = SafetyProfile(
        tool_violations=s_data.get("tool_violations", 0),
        text_violations=s_data.get("text_violations", 0),
        total_probes=s_data.get("total_probes", 0),
    )
    sc = data.get("scoring", {})
    dec = data.get("decision", {})
    report_obj = CheckpointReport(
        step=data.get("step", target_step),
        hypothesis=data.get("hypothesis", ""),
        commit=data.get("commit", ""),
        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
        training=metrics,
        process=process,
        safety=safety,
        quality_score=sc.get("quality", 0.0),
        operational_cost=sc.get("cost", 0.0),
        safety_penalty=sc.get("safety", 0.0),
        composite_reward=sc.get("reward", 0.0),
        keep=dec.get("keep", False),
        reason=dec.get("reason", ""),
    )

    out_dir = Path(args.output_dir) if args.output_dir else json_dir / f"report_{target_step}"
    writer = ExperimentReportWriter(report_dir=out_dir)
    out_path = writer.write(report_obj)
    print(f"[ti report] Report written to {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ti",
        description="Training Insights — autonomous experiment platform with multi-dimensional evaluation",
    )

    # Global options
    parser.add_argument("--results-file", default="results.tsv",
                        help="Path to results TSV (default: results.tsv)")
    parser.add_argument("--json-dir", default=None,
                        help="Directory for per-experiment JSON reports (default: <results-dir>/runs/)")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- status ---
    subparsers.add_parser("status", help="Show experiment dashboard")

    # --- analyze ---
    p_analyze = subparsers.add_parser("analyze", help="Extract insights from experiment history")
    p_analyze.add_argument("--output", "-o", default=None,
                           help="Write insights to this file (default: stdout)")

    # --- run ---
    p_run = subparsers.add_parser("run", help="Run one or more training experiments")
    p_run.add_argument("--hypothesis", "-H", default=None,
                       help="Hypothesis for this experiment (single-run mode)")
    p_run.add_argument("--loop", action="store_true",
                       help="Run autonomously in a loop until interrupted")
    p_run.add_argument("--max-experiments", type=int, default=None,
                       help="Maximum experiments in loop mode")
    p_run.add_argument("--train-cmd", default="uv run quick_train.py",
                       help="Training command (default: uv run quick_train.py)")
    p_run.add_argument("--cwd", default=None,
                       help="Working directory for training subprocess")
    p_run.add_argument("--timeout", type=int, default=600,
                       help="Training subprocess timeout in seconds (default: 600)")
    p_run.add_argument("--alpha", type=float, default=1.0, help="Quality weight (default: 1.0)")
    p_run.add_argument("--beta",  type=float, default=0.5, help="Cost weight (default: 0.5)")
    p_run.add_argument("--gamma", type=float, default=2.0, help="Safety weight (default: 2.0)")
    p_run.add_argument("--no-git", action="store_true",
                       help="Disable automatic git keep/discard")

    # --- report ---
    p_report = subparsers.add_parser("report", help="Generate unified markdown report for an experiment")
    p_report.add_argument("--step", type=int, default=None, help="Experiment step number")
    p_report.add_argument("--latest", action="store_true", help="Report on the latest experiment")
    p_report.add_argument("--output-dir", default=None, help="Output directory for report")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status":  cmd_status,
        "analyze": cmd_analyze,
        "run":     cmd_run,
        "report":  cmd_report,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args) or 0)


if __name__ == "__main__":
    main()
