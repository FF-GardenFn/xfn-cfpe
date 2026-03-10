"""
evaluation/report.py — bridge between CheckpointReport and core/report.py.

core/report.py (Karpathy) generates system-level markdown: environment,
hardware, git state, bloat metrics. It knows nothing about experiment scoring.

CheckpointReport (Farhat) captures composite reward, BPB, CORE, safety,
process rewards. It knows nothing about the system it ran on.

This module bridges them: one unified experiment artifact per run.

Usage:
    from training_insights.evaluation.report import ExperimentReportWriter

    writer = ExperimentReportWriter(report_dir=Path("reports/experiment_001"))
    writer.write(report, parse_result)   # produces experiment_001/report.md
"""
from __future__ import annotations

import sys
from pathlib import Path

from training_insights.evaluation.checkpoint_eval import CheckpointReport
from training_insights.evaluation.parser import ParseResult, RunStatus


class ExperimentReportWriter:
    """Writes a unified markdown report for a single experiment.

    Combines:
    - System context from core/report.py's generate_header()
    - Composite reward breakdown from CheckpointReport
    - Decision rationale with full gate trace
    - Process rewards summary (RL-O-CoV layer diagnostics)
    - Safety profile (CAI violation taxonomy)
    """

    def __init__(self, report_dir: Path, alpha: float = 1.0, beta: float = 0.5, gamma: float = 2.0):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

    def write(
        self,
        report: CheckpointReport,
        parse_result: ParseResult | None = None,
    ) -> Path:
        """Write experiment_report.md and return its path."""
        sections: list[str] = []

        # 1. System header from core/report.py (best-effort; skip if unavailable)
        sections.append(self._system_header())

        # 2. Experiment identity
        sections.append(self._identity_section(report))

        # 3. Training engine metrics
        sections.append(self._training_section(report, parse_result))

        # 4. Composite reward breakdown
        sections.append(self._scoring_section(report))

        # 5. Decision with full gate trace
        sections.append(self._decision_section(report))

        # 6. Process rewards (RL-O-CoV)
        sections.append(self._process_section(report))

        # 7. Safety profile (CAI taxonomy)
        sections.append(self._safety_section(report))

        output = "\n\n".join(s for s in sections if s.strip())
        out_path = self.report_dir / "experiment_report.md"
        out_path.write_text(output, encoding="utf-8")
        return out_path

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _system_header(self) -> str:
        try:
            # core/ is a sibling directory; add parent to path if needed
            parent = Path(__file__).parent.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            from core.report import generate_header  # type: ignore
            return generate_header()
        except Exception as exc:
            return f"# Training Insights — Experiment Report\n\n> system header unavailable: {exc}\n"

    def _identity_section(self, r: CheckpointReport) -> str:
        return (
            f"## Experiment #{r.step}\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Hypothesis | {r.hypothesis or '—'} |\n"
            f"| Commit | `{r.commit or 'unknown'}` |\n"
            f"| Timestamp | {r.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} |\n"
            f"| Decision | {'✓ **KEEP**' if r.keep else '✗ **DISCARD**'} |\n"
        )

    def _training_section(
        self,
        r: CheckpointReport,
        parse_result: ParseResult | None,
    ) -> str:
        m = r.training
        lines = [
            "## Training Engine Metrics\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| val_bpb | `{m.val_bpb:.6f}` |",
            f"| CORE score | `{m.core_score:.4f}` |",
            f"| MFU | `{m.mfu_pct:.1f}%` |",
            f"| Peak VRAM | `{m.peak_vram_gb:.1f} GB` |",
            f"| Wall time | `{m.wall_time_sec:.1f}s` |",
            f"| Tokens | `{m.total_tokens / 1e6:.1f}M` |",
        ]
        if parse_result:
            lines += [
                f"| Num steps | `{parse_result.num_steps:,}` |",
                f"| Model depth | `{parse_result.depth}` |",
                f"| Params | `{parse_result.num_params_M:.1f}M` |",
                f"| Run status | `{parse_result.status.value}` |",
            ]
            if parse_result.crash_hint:
                lines.append(f"\n> ⚠ **Run issue**: {parse_result.crash_hint}")
        return "\n".join(lines)

    def _scoring_section(self, r: CheckpointReport) -> str:
        # Infer weights from composite: R = α·Q − β·C − γ·S
        # If Q, C, S are all non-zero we can recover the weights; otherwise show defaults.
        alpha = self.alpha
        beta = self.beta
        gamma = self.gamma
        return (
            "## Composite Reward Breakdown\n\n"
            "```\n"
            f"R = α·quality − β·cost − γ·safety\n"
            f"  = {alpha} × {r.quality_score:.4f}  −  {beta} × {r.operational_cost:.4f}  −  {gamma} × {r.safety_penalty:.4f}\n"
            f"  = {r.composite_reward:+.4f}\n"
            "```\n\n"
            f"| Component | Weight | Raw Score | Weighted |\n"
            f"|-----------|--------|-----------|----------|\n"
            f"| Quality (BPB 60% + CORE 30% + MFU 10%) | α={alpha} | {r.quality_score:.4f} | {alpha * r.quality_score:+.4f} |\n"
            f"| Cost (time 70% + VRAM 30%) | β={beta} | {r.operational_cost:.4f} | {-beta * r.operational_cost:+.4f} |\n"
            f"| Safety (CAI violations) | γ={gamma} | {r.safety_penalty:.4f} | {-gamma * r.safety_penalty:+.4f} |\n"
            f"| **Composite R** | — | — | **{r.composite_reward:+.4f}** |\n"
        )

    def _decision_section(self, r: CheckpointReport) -> str:
        status_emoji = "✓" if r.keep else "✗"
        status_word = "KEEP" if r.keep else "DISCARD"
        return (
            f"## Decision: {status_emoji} {status_word}\n\n"
            f"> {r.reason}\n\n"
            "### Decision Gate Trace\n\n"
            "The evaluator applies gates in order; the first failing gate wins:\n\n"
            "1. **BPB validity** — crash/divergence detection\n"
            "2. **First run** — establishes composite + BPB baseline\n"
            "3. **Safety veto** — CAI penalty ≥ 0.5 discards unconditionally\n"
            "4. **BPB divergence floor** — regression > 5% discards unconditionally\n"
            "5. **Composite reward improvement** — Δ R > 0.001 → KEEP\n"
            "6. **BPB improved but composite did not** → DISCARD (cost/safety offset)\n"
            "7. **Default** → DISCARD\n"
        )

    def _process_section(self, r: CheckpointReport) -> str:
        p = r.process
        goldilocks = "✓ in zone" if p.goldilocks else "✗ outside zone"
        return (
            "## Process Rewards (RL-O-CoV)\n\n"
            "Measures *how* the model reasons, not just what it produces.\n"
            "Derived from hidden-state cosine similarity at the diagnostic layer.\n\n"
            f"| Signal | Value |\n"
            f"|--------|-------|\n"
            f"| Resonance | `{p.resonance:.4f}` |\n"
            f"| Structure | `{p.structure:.4f}` |\n"
            f"| Goldilocks zone | {goldilocks} |\n"
            f"| Diagnostic layer | `{p.layer_depth}` |\n\n"
            "> RL-O-CoV V3 lesson: layer depth determines whether cosine similarity\n"
            "> is informative (0.15–0.95) or degenerate (collapsed to 0 or 1).\n"
            "> Values outside the Goldilocks zone indicate representational collapse.\n"
        )

    def _safety_section(self, r: CheckpointReport) -> str:
        s = r.safety
        veto = " ← **SAFETY VETO TRIGGERED**" if r.safety_penalty >= 0.5 else ""
        return (
            "## Safety Profile (CAI Taxonomy)\n\n"
            "Violations detected via Constitutional AI probe taxonomy.\n"
            "Tool violations (score=5.0) are weighted higher than text violations (score=3.0).\n\n"
            f"| Category | Count |\n"
            f"|----------|-------|\n"
            f"| Tool violations | `{s.tool_violations}`{veto} |\n"
            f"| Text violations | `{s.text_violations}` |\n"
            f"| Refusal failures | `{s.refusal_failures}` |\n"
            f"| False refusals | `{s.false_refusals}` |\n"
            f"| Total probes | `{s.total_probes}` |\n"
            f"| Violation rate | `{s.violation_rate:.4f}` |\n"
            f"| Safety penalty | `{r.safety_penalty:.4f}` |\n\n"
            "> CAI inversion finding: self-critique increased violations on Sonnet (+1.6pp).\n"
            "> Capability improvement and safety are not monotonically related.\n"
        )
