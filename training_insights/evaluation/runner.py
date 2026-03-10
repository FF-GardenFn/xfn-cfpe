"""
ExperimentRunner — closes the loop between training and evaluation.

Before this module, the experiment cycle was 7 manual steps:
  1. run quick_train.py
  2. grep val_bpb from run.log
  3. manually compare to best in results.tsv
  4. decide keep/discard based only on BPB
  5. manually write TSV row
  6. git reset if discarding
  7. repeat

After this module, it is one call:
  runner = ExperimentRunner()
  report = runner.run_experiment(hypothesis="wider sliding window SSLL")

The runner:
  - Launches the training process with a watchdog timeout
  - Captures stdout to run.log
  - Calls the parser to extract TrainingMetrics
  - Calls CheckpointEvaluator (composite reward drives keep/discard)
  - Calls ExperimentTracker to log TSV + JSON
  - Executes git keep/discard automatically
  - Returns a full CheckpointReport for inspection

Usage:
    from training_insights.evaluation.runner import ExperimentRunner

    runner = ExperimentRunner(results_file=Path("results.tsv"))

    # One-shot: run training + evaluate + log + git
    report = runner.run_experiment(
        hypothesis="increase embedding_lr 0.6 → 0.8",
        train_cmd="uv run quick_train.py",
    )
    print(f"Decision: {'KEEP' if report.keep else 'DISCARD'}")
    print(f"Reason:   {report.reason}")
    print(f"Reward:   R={report.composite_reward:+.4f}")

    # Or: evaluate a log file from a run already completed
    report = runner.evaluate_output(
        "run.log",
        hypothesis="wider window SSLL",
        commit="abc1234",
    )
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from training_insights.evaluation.checkpoint_eval import (
    CheckpointEvaluator,
    CheckpointReport,
    ExperimentTracker,
    ProcessRewards,
    SafetyProfile,
)
from training_insights.evaluation.parser import ParseResult, RunStatus, parse_training_output

logger = logging.getLogger(__name__)

# Default time budget: 5-min training + 2-min overhead ceiling
_DEFAULT_TIMEOUT_SEC: int = 600
_DEFAULT_TRAIN_CMD: str = "uv run quick_train.py"
_DEFAULT_LOG_FILE: str = "run.log"


class ExperimentRunner:
    """Orchestrates the full experiment cycle: train → parse → evaluate → log → git.

    Parameters
    ----------
    results_file : Path
        TSV file where experiment results are accumulated. Created on first use.
    json_dir : Path | None
        Directory for per-experiment JSON reports. Defaults to results_file.parent/runs/
    baseline_bpb : float | None
        Seed the evaluator with a known baseline (e.g. from a previous session).
    alpha, beta, gamma : float
        ARENA composite reward weights (quality, cost, safety).
    timeout_sec : int
        Hard kill timeout for the training subprocess.
    auto_git : bool
        If True, automatically ``git reset --hard HEAD~1`` on discard and
        ``git add / commit`` records on keep. Set False if you want manual control.
    """

    def __init__(
        self,
        results_file: Path = Path("results.tsv"),
        json_dir: Path | None = None,
        baseline_bpb: float | None = None,
        baseline_composite: float | None = None,
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 2.0,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
        auto_git: bool = True,
    ):
        self.results_file = Path(results_file)
        self.json_dir = Path(json_dir) if json_dir else self.results_file.parent / "runs"
        self.timeout_sec = timeout_sec
        self.auto_git = auto_git

        self.evaluator = CheckpointEvaluator(
            baseline_bpb=baseline_bpb,
            baseline_composite=baseline_composite,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
        )
        self.tracker = ExperimentTracker(self.results_file)
        self._experiment_count = self.tracker.experiment_count()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        hypothesis: str,
        train_cmd: str = _DEFAULT_TRAIN_CMD,
        log_file: str = _DEFAULT_LOG_FILE,
        process_rewards: ProcessRewards | None = None,
        safety_profile: SafetyProfile | None = None,
        cwd: str | None = None,
    ) -> CheckpointReport:
        """Run a full experiment cycle end-to-end.

        Steps
        -----
        1. Run training subprocess (with watchdog timeout).
        2. Parse stdout → TrainingMetrics.
        3. Evaluate → CheckpointReport (composite reward drives decision).
        4. Log to TSV + JSON.
        5. Git keep (advance) or discard (reset) if auto_git=True.

        Returns the full CheckpointReport for inspection / logging.
        """
        self._experiment_count += 1
        step = self._experiment_count
        commit = self._git_short_hash(cwd=cwd)

        logger.info(
            "Experiment #%d | hypothesis: %s | commit: %s",
            step, hypothesis, commit,
        )

        # 1. Train
        t0 = time.time()
        run_ok = self._run_training(train_cmd, log_file, cwd=cwd)
        elapsed = time.time() - t0

        if not run_ok:
            logger.warning("Training subprocess failed or timed out after %.0fs", elapsed)

        # 2. Parse
        log_path = Path(cwd or ".") / log_file
        parse_result: ParseResult = parse_training_output(log_path)

        if parse_result.status in (RunStatus.CRASH, RunStatus.OOM, RunStatus.EMPTY, RunStatus.DIVERGE):
            logger.warning("Run #%d failed (%s): %s", step, parse_result.status.value, parse_result.crash_hint)
            report = self._crash_report(step, hypothesis, commit, parse_result)
            self.tracker.log(report)
            self.tracker.log_json(report, self.json_dir)
            # Failed run: revert the commit that changed the code
            if self.auto_git:
                self._git_reset(cwd=cwd)
            return report

        # 3. Evaluate
        report = self.evaluator.evaluate(
            training_metrics=parse_result.metrics,
            hypothesis=hypothesis,
            step=step,
            commit=commit,
            process_rewards=process_rewards,
            safety_profile=safety_profile,
        )

        # 4. Log
        self.tracker.log(report)
        self.tracker.log_json(report, self.json_dir)

        # 5. Git keep / discard
        if self.auto_git:
            if report.keep:
                logger.info("KEEP  R=%+.4f | %s", report.composite_reward, report.reason)
                # Branch advances — nothing to do (commit already exists)
            else:
                logger.info("DISCARD R=%+.4f | %s", report.composite_reward, report.reason)
                self._git_reset(cwd=cwd)

        self._print_summary(report, parse_result)
        return report

    def evaluate_output(
        self,
        log_source: str | Path,
        hypothesis: str = "",
        commit: str = "",
        process_rewards: ProcessRewards | None = None,
        safety_profile: SafetyProfile | None = None,
    ) -> CheckpointReport:
        """Evaluate an already-completed run from its log file or stdout string.

        Use this when training ran separately and you want to score it.
        """
        self._experiment_count += 1
        step = self._experiment_count

        parse_result = parse_training_output(log_source)

        if parse_result.status in (RunStatus.CRASH, RunStatus.OOM, RunStatus.EMPTY, RunStatus.DIVERGE):
            report = self._crash_report(step, hypothesis, commit, parse_result)
        else:
            report = self.evaluator.evaluate(
                training_metrics=parse_result.metrics,
                hypothesis=hypothesis,
                step=step,
                commit=commit,
                process_rewards=process_rewards,
                safety_profile=safety_profile,
            )

        self.tracker.log(report)
        self.tracker.log_json(report, self.json_dir)
        self._print_summary(report, parse_result)
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_training(
        self,
        cmd: str,
        log_file: str,
        cwd: str | None = None,
    ) -> bool:
        """Launch training, redirect stdout+stderr to log_file. Return True on success."""
        log_path = Path(cwd or ".") / log_file
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        try:
            with open(log_path, "w") as lf:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=cwd,
                )
                try:
                    proc.wait(timeout=self.timeout_sec)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    logger.warning("Training killed after %ds timeout", self.timeout_sec)
                    return False
            return proc.returncode == 0
        except Exception as exc:
            logger.error("Failed to launch training process: %s", exc)
            return False

    @staticmethod
    def _git_short_hash(cwd: str | None = None) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=cwd, timeout=5,
            )
            return result.stdout.strip() or "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _git_reset(cwd: str | None = None) -> None:
        """Revert the last commit (experiment hypothesis change).

        Uses ``git revert --no-edit HEAD`` instead of ``git reset --hard``
        to avoid destroying unrelated staged or unstaged work.  The revert
        creates a new commit that undoes only the experiment's changes,
        preserving full history and safety.
        """
        try:
            subprocess.run(
                ["git", "revert", "--no-edit", "HEAD"],
                cwd=cwd, timeout=15, check=True,
                capture_output=True,
            )
            logger.info("git revert HEAD (discard — non-destructive)")
        except subprocess.CalledProcessError as exc:
            logger.error("git revert failed: %s", exc.stderr)

    @staticmethod
    def _crash_report(
        step: int,
        hypothesis: str,
        commit: str,
        parse_result: ParseResult,
    ) -> CheckpointReport:
        from datetime import datetime
        return CheckpointReport(
            step=step,
            hypothesis=hypothesis,
            commit=commit,
            timestamp=datetime.utcnow(),
            training=parse_result.metrics,
            keep=False,
            reason=f"{parse_result.status.value}: {parse_result.crash_hint}",
        )

    @staticmethod
    def _print_summary(report: CheckpointReport, parse_result: ParseResult) -> None:
        status_str = "✓ KEEP  " if report.keep else "✗ DISCARD"
        print(
            f"\n[Experiment #{report.step}] {status_str}\n"
            f"  Hypothesis : {report.hypothesis}\n"
            f"  val_bpb    : {report.training.val_bpb:.6f}\n"
            f"  CORE score : {report.training.core_score:.4f}\n"
            f"  MFU        : {report.training.mfu_pct:.1f}%\n"
            f"  VRAM       : {report.training.peak_vram_gb:.1f} GB\n"
            f"  R (reward) : {report.composite_reward:+.4f}  "
            f"(Q={report.quality_score:.3f}  C={report.operational_cost:.3f}  "
            f"S={report.safety_penalty:.3f})\n"
            f"  Reason     : {report.reason}\n"
        )
