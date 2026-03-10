"""
InsightEngine — extracts training insights from experiment history.

This is the "Training Insights" part of the platform: turning accumulated
experiment data into *understanding* about what actually matters.

Karpathy's loop answers: "did BPB improve?"
InsightEngine answers:
  - Which hyperparameter families consistently improve composite reward?
  - Which families are dead-ends (consistently negative delta)?
  - Does capability improvement track with safety regression? (CAI inversion)
  - Where is the efficiency frontier — the Pareto-optimal quality/cost tradeoff?
  - What is the next best hypothesis, given what we've learned?

Data sources:
  - results.tsv: step, commit, val_bpb, core, mfu%, vram_gb, reward, status, hypothesis
  - runs/*.json: full CheckpointReport with safety profile, process rewards, etc.

Usage:
    from training_insights.evaluation.insights import InsightEngine

    engine = InsightEngine(results_file=Path("results.tsv"), json_dir=Path("runs"))
    insights = engine.analyze()
    print(insights.summary())              # human-readable summary
    print(insights.next_hypothesis_context())  # inject into agent prompt
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Hypothesis family classification
# ---------------------------------------------------------------------------

# Maps regex patterns in hypothesis strings → named hyperparameter family.
# Order matters: first match wins.
_FAMILY_PATTERNS: list[tuple[str, str]] = [
    (r"unembed(?:ding)?[_\s]?lr|unembed.*lr",            "unembedding_lr"),
    (r"embed(?:ding)?[_\s]?lr|embedding.*learning.rate", "embedding_lr"),
    (r"matrix[_\s]?lr|weight[_\s]?lr",                   "matrix_lr"),
    (r"scalar[_\s]?lr",                                   "scalar_lr"),
    (r"\blr\b|learning.rate",                             "learning_rate"),
    (r"window[_\s]?pattern|window.size|sliding.window|SSLL|SSSL|SLSL", "window_pattern"),
    (r"batch[_\s]?size|total[_\s]?batch",                 "batch_size"),
    (r"depth|n[_\s]?layer|num[_\s]?layer",                "depth"),
    (r"aspect[_\s]?ratio|width|n[_\s]?embd",              "width"),
    (r"warmdown|warmup",                                   "lr_schedule"),
    (r"weight[_\s]?decay",                                 "weight_decay"),
    (r"head[_\s]?dim|n[_\s]?head|kv[_\s]?head",           "attention_head"),
    (r"baseline|no.change",                                "baseline"),
]


def classify_hypothesis(hypothesis: str) -> str:
    """Return the hyperparameter family for a hypothesis string."""
    h = hypothesis.lower()
    for pattern, family in _FAMILY_PATTERNS:
        if re.search(pattern, h):
            return family
    return "other"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExperimentRecord:
    """A single row from results.tsv enriched with JSON data if available."""
    step: int
    commit: str
    val_bpb: float
    core_score: float
    mfu_pct: float
    vram_gb: float
    composite_reward: float
    keep: bool
    hypothesis: str
    family: str
    # From JSON (optional)
    safety_penalty: float = 0.0
    quality_score: float = 0.0
    operational_cost: float = 0.0
    process_resonance: float = 0.0
    wall_time_sec: float = 0.0


@dataclass
class FamilyStats:
    """Aggregated stats for a hyperparameter family."""
    family: str
    n_experiments: int = 0
    n_kept: int = 0
    mean_reward_delta: float = 0.0
    best_reward: float = float("-inf")
    worst_reward: float = float("inf")
    mean_bpb_delta: float = 0.0
    mean_safety_delta: float = 0.0
    verdict: str = "unknown"   # "promising" | "dead_end" | "neutral" | "insufficient_data"


@dataclass
class ParetoPoint:
    """A point on the quality-cost Pareto frontier."""
    step: int
    hypothesis: str
    quality: float
    cost: float
    reward: float
    val_bpb: float
    is_pareto_optimal: bool = False


@dataclass
class SafetyDriftReport:
    """Safety trajectory over the experiment history."""
    baseline_safety: float = 0.0
    current_safety: float = 0.0
    drift: float = 0.0           # positive = more violations over time
    inversion_detected: bool = False   # capability improved while safety worsened
    inversion_magnitude: float = 0.0   # Δ safety at point of best BPB improvement
    worst_experiment: str = ""


@dataclass
class InsightReport:
    """Full insight extraction result from experiment history."""
    n_total: int = 0
    n_kept: int = 0
    n_discarded: int = 0
    n_crashed: int = 0
    best_bpb: float = float("inf")
    best_reward: float = float("-inf")
    best_hypothesis: str = ""

    family_stats: list[FamilyStats] = field(default_factory=list)
    pareto_frontier: list[ParetoPoint] = field(default_factory=list)
    safety_drift: SafetyDriftReport = field(default_factory=SafetyDriftReport)
    dead_ends: list[str] = field(default_factory=list)
    promising_families: list[str] = field(default_factory=list)

    # Raw records for further analysis
    records: list[ExperimentRecord] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of all insights."""
        lines = [
            "# Training Insights — Experiment History Analysis",
            "",
            f"## Overview",
            f"- Total experiments: {self.n_total}",
            f"- Kept: {self.n_kept} ({100*self.n_kept/max(1,self.n_total):.0f}%)",
            f"- Discarded: {self.n_discarded}",
            f"- Crashed: {self.n_crashed}",
            f"- Best val_bpb: {self.best_bpb:.6f}",
            f"- Best composite R: {self.best_reward:+.4f}",
            f"- Best hypothesis: {self.best_hypothesis}",
            "",
            "## Hyperparameter Family Attribution",
        ]

        for fs in sorted(self.family_stats, key=lambda x: x.mean_reward_delta, reverse=True):
            verdict_icon = {"promising": "✓", "dead_end": "✗", "neutral": "~", "insufficient_data": "?"}.get(fs.verdict, "?")
            lines.append(
                f"- {verdict_icon} **{fs.family}**: {fs.n_experiments} experiments, "
                f"{fs.n_kept} kept, mean ΔR={fs.mean_reward_delta:+.4f} → {fs.verdict}"
            )

        lines += [
            "",
            "## Promising Directions",
            *(([f"- {f}" for f in self.promising_families]) or ["- (insufficient data)"]),
            "",
            "## Dead Ends (prune from future suggestions)",
            *(([f"- {f}" for f in self.dead_ends]) or ["- (none identified yet)"]),
            "",
            "## Safety Drift",
            f"- Baseline safety penalty: {self.safety_drift.baseline_safety:.4f}",
            f"- Current safety penalty:  {self.safety_drift.current_safety:.4f}",
            f"- Drift: {self.safety_drift.drift:+.4f}",
        ]

        if self.safety_drift.inversion_detected:
            lines += [
                f"- ⚠ **CAI INVERSION DETECTED**: capability improved while safety worsened",
                f"  Inversion magnitude: {self.safety_drift.inversion_magnitude:+.4f}",
                f"  Worst experiment: {self.safety_drift.worst_experiment}",
            ]
        else:
            lines.append("- No safety inversion detected.")

        if self.pareto_frontier:
            lines += [
                "",
                "## Efficiency Pareto Frontier (quality vs cost)",
                "Pareto-optimal experiments — best quality for their cost level:",
            ]
            for p in self.pareto_frontier:
                if p.is_pareto_optimal:
                    lines.append(
                        f"  - Exp #{p.step}: Q={p.quality:.3f} C={p.cost:.3f} "
                        f"R={p.reward:+.4f} BPB={p.val_bpb:.6f} | {p.hypothesis}"
                    )

        return "\n".join(lines)

    def next_hypothesis_context(self) -> str:
        """Structured context block for injection into the agent's next hypothesis prompt."""
        promising = ", ".join(self.promising_families) or "insufficient data"
        dead = ", ".join(self.dead_ends) or "none"
        inversion = (
            f"⚠ CAI inversion detected (magnitude={self.safety_drift.inversion_magnitude:+.4f}). "
            "Prioritise experiments that do not increase safety penalty."
            if self.safety_drift.inversion_detected
            else "No safety inversion. Safety headroom available."
        )

        # Top-3 best kept experiments
        top3 = sorted(
            [r for r in self.records if r.keep],
            key=lambda x: x.composite_reward,
            reverse=True,
        )[:3]
        top3_lines = "\n".join(
            f"  {i+1}. {r.hypothesis} → R={r.composite_reward:+.4f}, BPB={r.val_bpb:.6f}"
            for i, r in enumerate(top3)
        ) or "  (none kept yet)"

        return f"""## Insight Context for Next Hypothesis

**Experiment history**: {self.n_total} total, {self.n_kept} kept, best BPB={self.best_bpb:.6f}

**Promising hyperparameter families** (positive mean ΔR): {promising}
**Dead-end families** (prune — consistently negative ΔR): {dead}

**Top-3 kept experiments**:
{top3_lines}

**Safety status**: {inversion}

**Efficiency frontier**: The Pareto-optimal experiments balance quality and cost.
Avoid hypotheses that trade large VRAM/time increases for marginal BPB gains.

**Suggested next direction**: Focus on {promising.split(',')[0].strip() if promising != 'insufficient data' else 'establishing baseline'}.
Avoid: {dead}.
"""


# ---------------------------------------------------------------------------
# InsightEngine
# ---------------------------------------------------------------------------

class InsightEngine:
    """Extracts training insights from accumulated experiment history.

    Parameters
    ----------
    results_file : Path
        Path to results.tsv (the experiment log).
    json_dir : Path | None
        Directory containing per-experiment JSON files (from ExperimentTracker).
        If provided, enriches records with safety/process reward data.
    min_experiments_for_verdict : int
        Minimum experiments in a family before issuing promising/dead_end verdict.
    """

    def __init__(
        self,
        results_file: Path = Path("results.tsv"),
        json_dir: Path | None = None,
        min_experiments_for_verdict: int = 2,
    ):
        self.results_file = Path(results_file)
        self.json_dir = Path(json_dir) if json_dir else None
        self.min_n = min_experiments_for_verdict

    def analyze(self) -> InsightReport:
        """Run full analysis. Returns InsightReport with all insights."""
        records = self._load_records()
        if not records:
            return InsightReport()

        report = InsightReport(
            n_total=len(records),
            n_kept=sum(1 for r in records if r.keep),
            n_discarded=sum(1 for r in records if not r.keep and r.val_bpb > 0),
            n_crashed=sum(1 for r in records if r.val_bpb <= 0),
            records=records,
        )

        kept = [r for r in records if r.keep]
        if kept:
            best = min(kept, key=lambda r: r.val_bpb)
            report.best_bpb = best.val_bpb
            report.best_reward = max(r.composite_reward for r in kept)
            report.best_hypothesis = best.hypothesis

        report.family_stats = self._family_attribution(records)
        report.promising_families = [
            fs.family for fs in report.family_stats if fs.verdict == "promising"
        ]
        report.dead_ends = [
            fs.family for fs in report.family_stats if fs.verdict == "dead_end"
        ]
        report.pareto_frontier = self._pareto_frontier(records)
        report.safety_drift = self._safety_drift(records)

        return report

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_records(self) -> list[ExperimentRecord]:
        if not self.results_file.exists():
            return []

        lines = self.results_file.read_text().strip().splitlines()
        if len(lines) < 2:
            return []

        records: list[ExperimentRecord] = []
        json_index = self._index_json_files() if self.json_dir else {}

        for line in lines[1:]:   # skip header
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            try:
                step      = int(parts[0])
                commit    = parts[1]
                val_bpb   = float(parts[2])
                core      = float(parts[3])
                mfu_pct   = float(parts[4])
                vram_gb   = float(parts[5])
                reward    = float(parts[6])
                keep      = parts[7].strip().lower() == "keep"
                hypothesis = parts[8].strip() if len(parts) > 8 else ""
            except (ValueError, IndexError):
                continue

            rec = ExperimentRecord(
                step=step,
                commit=commit,
                val_bpb=val_bpb,
                core_score=core,
                mfu_pct=mfu_pct,
                vram_gb=vram_gb,
                composite_reward=reward,
                keep=keep,
                hypothesis=hypothesis,
                family=classify_hypothesis(hypothesis),
            )

            # Enrich from JSON if available
            json_data = json_index.get(step) or json_index.get(commit)
            if json_data:
                scoring = json_data.get("scoring", {})
                rec.safety_penalty   = scoring.get("safety", 0.0)
                rec.quality_score    = scoring.get("quality", 0.0)
                rec.operational_cost = scoring.get("cost", 0.0)
                pr = json_data.get("process_rewards", {})
                rec.process_resonance = pr.get("resonance", 0.0)
                tr = json_data.get("training", {})
                rec.wall_time_sec = tr.get("wall_time_sec", 0.0)

            records.append(rec)

        return records

    def _index_json_files(self) -> dict[Any, dict]:
        """Build a lookup: step → parsed JSON, commit → parsed JSON."""
        index: dict[Any, dict] = {}
        if not self.json_dir or not self.json_dir.exists():
            return index
        for fp in self.json_dir.glob("experiment_*.json"):
            try:
                data = json.loads(fp.read_text())
                step = data.get("step")
                commit = data.get("commit")
                if step is not None:
                    index[step] = data
                if commit:
                    index[commit] = data
            except Exception:
                continue
        return index

    # ------------------------------------------------------------------
    # Analysis methods
    # ------------------------------------------------------------------

    def _family_attribution(self, records: list[ExperimentRecord]) -> list[FamilyStats]:
        """Compute per-family reward statistics."""
        # Compute per-experiment reward delta vs. the rolling best at that point
        rolling_best = float("inf")
        bpb_at_baseline: float | None = None
        deltas: list[tuple[ExperimentRecord, float]] = []

        for r in records:
            if bpb_at_baseline is None and r.val_bpb > 0:
                bpb_at_baseline = r.val_bpb
                rolling_best = r.composite_reward
                deltas.append((r, 0.0))
                continue
            if r.val_bpb > 0:
                delta = r.composite_reward - rolling_best
                deltas.append((r, delta))
                if r.keep:
                    rolling_best = max(rolling_best, r.composite_reward)

        by_family: dict[str, list[tuple[ExperimentRecord, float]]] = defaultdict(list)
        for r, delta in deltas:
            by_family[r.family].append((r, delta))

        stats: list[FamilyStats] = []
        for family, items in by_family.items():
            n = len(items)
            n_kept = sum(1 for r, _ in items if r.keep)
            reward_deltas = [delta for _, delta in items]
            mean_delta = sum(reward_deltas) / n
            # Compute actual BPB deltas (lower = better, so baseline - current = improvement)
            bpb_values = [r.val_bpb for r, _ in items if r.val_bpb > 0]

            if n < self.min_n:
                verdict = "insufficient_data"
            elif mean_delta > 0.005:
                verdict = "promising"
            elif mean_delta < -0.01:
                verdict = "dead_end"
            else:
                verdict = "neutral"

            stats.append(FamilyStats(
                family=family,
                n_experiments=n,
                n_kept=n_kept,
                mean_reward_delta=mean_delta,
                best_reward=max(r.composite_reward for r, _ in items),
                worst_reward=min(r.composite_reward for r, _ in items),
                mean_bpb_delta=(
                    sum((bpb_at_baseline or 0) - v for v in bpb_values) / len(bpb_values)
                    if bpb_values and bpb_at_baseline else 0.0
                ),
                verdict=verdict,
            ))

        return stats

    def _pareto_frontier(self, records: list[ExperimentRecord]) -> list[ParetoPoint]:
        """Find quality-cost Pareto-optimal experiments among kept checkpoints."""
        kept = [r for r in records if r.keep and r.quality_score > 0]
        if not kept:
            # Fall back to approximating quality from BPB and reward
            kept_all = [r for r in records if r.keep and r.val_bpb > 0]
            if not kept_all:
                return []
            min_bpb = min(r.val_bpb for r in kept_all)
            points = [
                ParetoPoint(
                    step=r.step,
                    hypothesis=r.hypothesis,
                    quality=1.0 - (r.val_bpb - min_bpb),
                    cost=r.vram_gb / 80.0,
                    reward=r.composite_reward,
                    val_bpb=r.val_bpb,
                )
                for r in kept_all
            ]
        else:
            points = [
                ParetoPoint(
                    step=r.step,
                    hypothesis=r.hypothesis,
                    quality=r.quality_score,
                    cost=r.operational_cost,
                    reward=r.composite_reward,
                    val_bpb=r.val_bpb,
                )
                for r in kept
            ]

        # Mark Pareto-optimal: no other point dominates (higher Q AND lower C)
        for i, p in enumerate(points):
            dominated = any(
                other.quality >= p.quality and other.cost <= p.cost and other is not p
                for other in points
            )
            p.is_pareto_optimal = not dominated

        return points

    def _safety_drift(self, records: list[ExperimentRecord]) -> SafetyDriftReport:
        """Detect safety drift and capability-safety inversions."""
        safety_records = [r for r in records if r.safety_penalty > 0 or r.val_bpb > 0]
        if len(safety_records) < 2:
            return SafetyDriftReport()

        first = safety_records[0]
        last = safety_records[-1]
        drift = last.safety_penalty - first.safety_penalty

        # Inversion: find experiments where BPB improved but safety worsened
        # relative to the previous kept checkpoint
        prev_kept_bpb = None
        prev_kept_safety = None
        inversion_magnitude = 0.0
        worst_exp = ""
        inversion_detected = False

        for r in records:
            if not r.keep:
                continue
            if prev_kept_bpb is not None:
                bpb_improved = r.val_bpb < prev_kept_bpb
                safety_worsened = r.safety_penalty > (prev_kept_safety or 0.0)
                if bpb_improved and safety_worsened:
                    magnitude = r.safety_penalty - (prev_kept_safety or 0.0)
                    if magnitude > inversion_magnitude:
                        inversion_magnitude = magnitude
                        worst_exp = r.hypothesis
                        inversion_detected = True
            prev_kept_bpb = r.val_bpb
            prev_kept_safety = r.safety_penalty

        return SafetyDriftReport(
            baseline_safety=first.safety_penalty,
            current_safety=last.safety_penalty,
            drift=drift,
            inversion_detected=inversion_detected,
            inversion_magnitude=inversion_magnitude,
            worst_experiment=worst_exp,
        )
