"""ARENA Debate Runner — full scoring pipeline with aggregation.

Wires DebateProtocol → RubricScorer → CostModel → CompositeReward into a
single execution pipeline. Produces per-debate scoring and cross-task
aggregation reports.

Pipeline:
    Task → DebateProtocol.run() → DebateResult
                                      ↓
                              RubricScorer.score_llm()  → RubricScore (8 dimensions)
                              CostModel.compute()       → CostBreakdown (5 components)
                                      ↓
                              CompositeReward.compute()  → RewardBreakdown
                                      ↓
                              R = α·quality − β·cost − γ·safety

Usage:
    python -m ARENA.runners.debate_runner --task crux_01_acquisition
    python -m ARENA.runners.debate_runner --suite --categories crux_identification
    python -m ARENA.runners.debate_runner --suite --proposer gpt4o --opponent claude
    python -m ARENA.runners.debate_runner --suite --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime
from itertools import groupby
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ARENA.protocols.base import ProtocolTurn, Role
from ARENA.protocols.debate import (
    DebateConfig,
    DebateProtocol,
    DebateResult,
    ModelConfig,
)
from ARENA.scoring.cost_model import CostBreakdown, CostModel
from ARENA.scoring.reward import CompositeReward, RewardBreakdown
from ARENA.scoring.rubric import RubricScore, RubricScorer
from ARENA.tasks.seed_tasks import SEED_TASKS, ArenaTask, TaskCategory

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL PRESETS
# =============================================================================

MODEL_PRESETS: dict[str, ModelConfig] = {
    "claude": ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514"),
    "claude-opus": ModelConfig(provider="anthropic", model="claude-opus-4-5-20251101"),
    "claude-haiku": ModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
    "gemini": ModelConfig(provider="google", model="gemini-2.5-flash"),
    "gemini-pro": ModelConfig(provider="google", model="gemini-1.5-pro"),
    "gpt4o": ModelConfig(provider="openai", model="gpt-4o"),
    "grok": ModelConfig(provider="xai", model="grok-2-1212"),
}

DEFAULT_JUDGE = "claude-opus"


# =============================================================================
# SCORING DATA MODELS
# =============================================================================


@dataclass
class DebateScoring:
    """Complete scoring for a single debate — rubric + cost + reward."""

    rubric: RubricScore
    cost: CostBreakdown
    reward: RewardBreakdown

    @property
    def quality(self) -> float:
        return self.reward.quality_score

    @property
    def total_cost_usd(self) -> float:
        return self.cost.total_cost_usd

    @property
    def total_reward(self) -> float:
        return self.reward.total_reward


@dataclass
class ScoredDebate:
    """A debate result paired with its scoring pipeline output."""

    result: DebateResult
    task: ArenaTask
    scoring: DebateScoring | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    @property
    def winner(self) -> str:
        return self.result.winner if self.result else ""


@dataclass
class ModelPerformance:
    """Aggregated stats for one model across a debate suite."""

    model: str
    role: str
    debates: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    avg_quality: float = 0.0
    avg_reward: float = 0.0
    avg_cost_usd: float = 0.0
    total_tokens: int = 0
    total_thinking_tokens: int = 0
    avg_latency_ms: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.debates if self.debates else 0.0


@dataclass
class SuiteReport:
    """Aggregated report across a full debate suite."""

    debates: list[ScoredDebate]
    model_performance: dict[str, ModelPerformance]
    category_stats: dict[str, dict[str, float]]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def succeeded(self) -> list[ScoredDebate]:
        return [d for d in self.debates if d.succeeded]

    @property
    def failed(self) -> list[ScoredDebate]:
        return [d for d in self.debates if not d.succeeded]

    @property
    def success_rate(self) -> float:
        return len(self.succeeded) / len(self.debates) if self.debates else 0.0


# =============================================================================
# SCORING PIPELINE
# =============================================================================


def _extract_tokens(
    turns: Sequence[ProtocolTurn],
    role: Role | None = None,
) -> tuple[int, int, int]:
    """Sum (input, output, thinking) tokens from turns, optionally by role."""
    input_t = output_t = thinking_t = 0
    for t in turns:
        if role is not None and t.role != role:
            continue
        input_t += t.metadata.get("input_tokens", 0)
        output_t += t.metadata.get("output_tokens", 0)
        thinking_t += t.thinking_tokens
    return input_t, output_t, thinking_t


def _final_argument(result: DebateResult) -> str:
    """Extract the proposer's last argument as the scorable response.

    In a debate, the proposer's final round — after integrating opponent
    challenges — is the strongest signal of reasoning quality.
    """
    for turn in reversed(result.turns):
        if turn.role == Role.PROPOSER:
            return turn.content
    return ""


def score_debate(
    result: DebateResult,
    task: ArenaTask,
    *,
    scorer: RubricScorer | None = None,
    cost_model: CostModel | None = None,
    reward_fn: CompositeReward | None = None,
    use_heuristic: bool = False,
) -> DebateScoring:
    """Score a completed debate through the full pipeline.

    Pipeline: DebateResult → RubricScore → CostBreakdown → RewardBreakdown

    The rubric evaluates the *output quality* of the proposer's final argument
    (8 dimensions). This is independent of the debate judge's 5-dimension
    scoring of the *debate process*. Both matter: the judge scores how well
    models debated; the rubric scores what was produced.

    Args:
        result: Completed debate with transcript.
        task: Original task (provides context for rubric scoring).
        scorer: RubricScorer instance (created with defaults if None).
        cost_model: CostModel instance (created with defaults if None).
        reward_fn: CompositeReward instance (created with defaults if None).
        use_heuristic: Use fast heuristic scoring instead of LLM judge.

    Returns:
        DebateScoring with rubric, cost, and reward components.
    """
    scorer = scorer or RubricScorer()
    cost_model = cost_model or CostModel()
    reward_fn = reward_fn or CompositeReward()

    # --- Rubric: score the proposer's final argument ---
    response = _final_argument(result)
    rubric = (
        scorer.score_heuristic(response)
        if use_heuristic
        else scorer.score_llm(task.question, response)
    )

    # --- Cost: aggregate tokens across all debate turns ---
    input_tokens, output_tokens, thinking_tokens = _extract_tokens(result.turns)
    debate_turns = sum(1 for t in result.turns if t.role != Role.JUDGE)

    cost = cost_model.compute(
        model=result.proposer_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        num_turns=debate_turns,
    )

    # --- Reward: combine quality, cost, and safety into scalar ---
    reward = reward_fn.compute(
        dimension_scores=rubric.dimensions,
        cost_breakdown=cost,
        safety_violations=[],
        hard_fails=rubric.hard_fails,
    )

    return DebateScoring(rubric=rubric, cost=cost, reward=reward)


# =============================================================================
# DEBATE EXECUTION
# =============================================================================


def run_debate(
    task: ArenaTask,
    proposer_key: str = "claude",
    opponent_key: str = "gemini",
    judge_key: str = DEFAULT_JUDGE,
    config: DebateConfig | None = None,
    *,
    score: bool = True,
    use_heuristic: bool = False,
) -> ScoredDebate:
    """Execute a single debate with optional scoring pipeline.

    Args:
        task: ArenaTask to debate.
        proposer_key: Key into MODEL_PRESETS for proposer.
        opponent_key: Key into MODEL_PRESETS for opponent.
        judge_key: Key into MODEL_PRESETS for judge.
        config: Debate configuration (rounds, token limits).
        score: Run the scoring pipeline (rubric + cost + reward).
        use_heuristic: Use heuristic scoring (no extra LLM call).

    Returns:
        ScoredDebate with result and scoring (if enabled).
    """
    proposer = MODEL_PRESETS[proposer_key]
    opponent = MODEL_PRESETS[opponent_key]
    judge = MODEL_PRESETS[judge_key]

    _print_header(task, proposer, opponent, judge)

    protocol = DebateProtocol(
        proposer=proposer,
        opponent=opponent,
        judge=judge,
        config=config or DebateConfig(),
    )

    try:
        result = protocol.run(task)
    except Exception as e:
        logger.error(f"Debate failed for {task.id}: {e}")
        empty = DebateResult(protocol_name="debate", task_id=task.id)
        scored = ScoredDebate(result=empty, task=task, error=str(e))
        _print_result(scored)
        return scored

    scoring = None
    if score:
        try:
            scoring = score_debate(result, task, use_heuristic=use_heuristic)
        except Exception as e:
            logger.error(f"Scoring failed for {task.id}: {e}")

    scored = ScoredDebate(result=result, task=task, scoring=scoring)
    _print_result(scored)
    return scored


def run_suite(
    tasks: Sequence[ArenaTask],
    proposer_key: str = "claude",
    opponent_key: str = "gemini",
    judge_key: str = DEFAULT_JUDGE,
    config: DebateConfig | None = None,
    *,
    score: bool = True,
    use_heuristic: bool = False,
) -> SuiteReport:
    """Execute debates across multiple tasks with aggregation.

    Individual failures don't halt the suite — errors are captured per-debate
    and the report includes both succeeded and failed runs.

    Args:
        tasks: Sequence of ArenaTask to run.
        proposer_key: Proposer model preset key.
        opponent_key: Opponent model preset key.
        judge_key: Judge model preset key.
        config: Shared debate configuration.
        score: Run scoring pipeline per debate.
        use_heuristic: Use heuristic scoring.

    Returns:
        SuiteReport with per-debate results, model stats, and category breakdown.
    """
    debates: list[ScoredDebate] = []

    for i, task in enumerate(tasks, 1):
        print(f"\n{'━' * 70}")
        print(f"  Task {i}/{len(tasks)}")
        print(f"{'━' * 70}")

        scored = run_debate(
            task=task,
            proposer_key=proposer_key,
            opponent_key=opponent_key,
            judge_key=judge_key,
            config=config,
            score=score,
            use_heuristic=use_heuristic,
        )
        debates.append(scored)

    report = aggregate_results(
        debates,
        proposer_model=MODEL_PRESETS[proposer_key].model,
        opponent_model=MODEL_PRESETS[opponent_key].model,
    )
    _print_report(report)
    return report


# =============================================================================
# AGGREGATION
# =============================================================================


def aggregate_results(
    debates: Sequence[ScoredDebate],
    proposer_model: str = "",
    opponent_model: str = "",
) -> SuiteReport:
    """Aggregate scored debates into a suite report.

    Computes per-model win/loss/draw rates, quality and cost averages,
    and per-category discriminative power distributions.
    """
    succeeded = [d for d in debates if d.succeeded]

    # --- Per-model performance ---
    model_perf: dict[str, ModelPerformance] = {}
    if proposer_model:
        model_perf[proposer_model] = _model_stats(
            succeeded, proposer_model, "proposer",
        )
    if opponent_model:
        model_perf[opponent_model] = _model_stats(
            succeeded, opponent_model, "opponent",
        )

    # --- Per-category stats ---
    category_stats: dict[str, dict[str, float]] = {}
    keyfunc = lambda d: d.task.category.value
    for category, group in groupby(sorted(succeeded, key=keyfunc), key=keyfunc):
        group_list = list(group)
        scored = [d for d in group_list if d.scoring]

        stats: dict[str, float] = {"count": len(group_list)}
        if scored:
            qualities = [d.scoring.quality for d in scored]
            rewards = [d.scoring.total_reward for d in scored]
            disc = [
                d.result.discriminative_power
                for d in scored
                if d.result.discriminative_power > 0
            ]
            stats["avg_quality"] = statistics.mean(qualities)
            stats["avg_reward"] = statistics.mean(rewards)
            stats["quality_stdev"] = (
                statistics.stdev(qualities) if len(qualities) > 1 else 0.0
            )
            stats["avg_discriminative_power"] = (
                statistics.mean(disc) if disc else 0.0
            )

        category_stats[category] = stats

    return SuiteReport(
        debates=list(debates),
        model_performance=model_perf,
        category_stats=category_stats,
    )


def _model_stats(
    debates: Sequence[ScoredDebate],
    model: str,
    role: str,
) -> ModelPerformance:
    """Compute aggregated performance for one model in one role."""
    perf = ModelPerformance(model=model, role=role, debates=len(debates))
    if not debates:
        return perf

    # Win/draw/loss
    for d in debates:
        if d.result.winner == role:
            perf.wins += 1
        elif d.result.winner == "draw":
            perf.draws += 1
        else:
            perf.losses += 1

    # Tokens from turns matching this role
    role_enum = Role.PROPOSER if role == "proposer" else Role.OPPONENT
    role_turns = [
        t for d in debates for t in d.result.turns if t.role == role_enum
    ]
    perf.total_tokens = sum(t.tokens_used for t in role_turns)
    perf.total_thinking_tokens = sum(t.thinking_tokens for t in role_turns)
    if role_turns:
        perf.avg_latency_ms = statistics.mean(t.latency_ms for t in role_turns)

    # Quality and cost from scoring pipeline
    scored = [d for d in debates if d.scoring]
    if scored:
        perf.avg_quality = statistics.mean(d.scoring.quality for d in scored)
        perf.avg_reward = statistics.mean(d.scoring.total_reward for d in scored)
        perf.avg_cost_usd = statistics.mean(d.scoring.total_cost_usd for d in scored)

    return perf


# =============================================================================
# DISPLAY
# =============================================================================


def _print_header(
    task: ArenaTask,
    proposer: ModelConfig,
    opponent: ModelConfig,
    judge: ModelConfig,
) -> None:
    print(f"\n{'=' * 70}")
    print(f"  ARENA DEBATE: {task.id}")
    print(f"  {task.category.value} | {task.difficulty.value}")
    print(f"{'=' * 70}")
    print(f"  Q: {task.question[:75]}{'...' if len(task.question) > 75 else ''}")
    print(f"  Proposer : {proposer.model}")
    print(f"  Opponent : {opponent.model}")
    print(f"  Judge    : {judge.model}")
    print(f"{'=' * 70}")


def _print_result(scored: ScoredDebate) -> None:
    """Print single debate result with full scoring breakdown."""
    if scored.error:
        print(f"\n  ERROR: {scored.error}")
        return

    r = scored.result
    _trunc = lambda s, n=70: f"{s[:n]}..." if len(s) > n else s

    print(f"\n{'─' * 50}")
    print(f"  Winner   : {r.winner}")
    print(f"  Crux     : {_trunc(r.crux)}")
    print(f"  Pre-mort : {_trunc(r.pre_mortem)}")
    print(f"  Disc.Pwr : {r.discriminative_power}/10")
    print(f"  Turns    : {r.num_turns}  |  Tokens: {r.total_tokens:,}")

    # Judge's debate-process scores (5 dimensions × 2 participants)
    if r.scores:
        print(f"\n  Judge Scores (debate process):")
        for side in ("proposer", "opponent"):
            dims = {
                k.removeprefix(f"{side}_"): v
                for k, v in r.scores.items()
                if k.startswith(side)
            }
            if dims:
                dim_str = "  ".join(f"{k}={v:.0f}" for k, v in dims.items())
                print(f"    {side:>8}: {dim_str}  (Σ={sum(dims.values()):.0f})")

    # Scoring pipeline output (rubric + cost + reward)
    if scored.scoring:
        s = scored.scoring
        hf = " HARD FAIL" if s.reward.hard_fail else ""
        print(f"\n  Scoring Pipeline:")
        print(f"    Quality  : {s.quality:.3f}{hf}")

        # Rubric dimension breakdown
        top_dims = sorted(
            s.rubric.dimensions.items(), key=lambda kv: kv[1], reverse=True,
        )
        dim_str = "  ".join(f"{k}={v:.0f}" for k, v in top_dims[:4])
        print(f"    Rubric   : {dim_str}  ...")

        # Cost breakdown
        print(f"    Cost     : ${s.total_cost_usd:.4f}")
        print(f"      tokens : ${s.cost.token_cost_usd:.4f}"
              f"  ({s.cost.input_tokens:,}in + {s.cost.output_tokens:,}out)")
        print(f"      turns  : ${s.cost.turn_cost_usd:.4f}")

        # Composite reward
        print(f"    Reward   : {s.total_reward:+.3f}")
        print(f"      R = {s.reward.quality_score:.3f}α"
              f" − {s.reward.operational_cost:.3f}β"
              f" − {s.reward.safety_penalty:.3f}γ")

        if s.rubric.hard_fails:
            print(f"    Hard Fails: {', '.join(s.rubric.hard_fails)}")

    print(f"{'─' * 50}")


def _print_report(report: SuiteReport) -> None:
    """Print aggregated suite report."""
    print(f"\n{'━' * 70}")
    print(f"  SUITE REPORT")
    print(f"  {len(report.succeeded)}/{len(report.debates)} debates completed"
          f"  ({report.success_rate:.0%} success)")
    print(f"{'━' * 70}")

    # Per-model performance
    if report.model_performance:
        print(f"\n  Model Performance:")
        for model, perf in report.model_performance.items():
            print(f"\n    {model} ({perf.role}):")
            print(f"      W/D/L      : {perf.wins}/{perf.draws}/{perf.losses}"
                  f"  ({perf.win_rate:.0%} win rate)")
            print(f"      Avg Quality: {perf.avg_quality:.3f}")
            print(f"      Avg Reward : {perf.avg_reward:+.3f}")
            print(f"      Avg Cost   : ${perf.avg_cost_usd:.4f}")
            print(f"      Tokens     : {perf.total_tokens:,}"
                  f"  (thinking: {perf.total_thinking_tokens:,})")
            if perf.avg_latency_ms:
                print(f"      Latency    : {perf.avg_latency_ms:.0f}ms avg")

    # Per-category breakdown
    if report.category_stats:
        print(f"\n  Category Breakdown:")
        for cat, stats in sorted(report.category_stats.items()):
            n = stats.get("count", 0)
            print(f"\n    {cat}  (n={n:.0f}):")
            if "avg_quality" in stats:
                print(f"      Quality : {stats['avg_quality']:.3f}"
                      f" ± {stats.get('quality_stdev', 0):.3f}")
                print(f"      Reward  : {stats['avg_reward']:+.3f}")
                disc = stats.get("avg_discriminative_power", 0)
                print(f"      Disc.Pwr: {disc:.1f}/10")

    # Failure summary
    if report.failed:
        print(f"\n  Failed Debates ({len(report.failed)}):")
        for d in report.failed:
            print(f"    {d.task.id}: {d.error}")

    print(f"\n{'━' * 70}")


# =============================================================================
# SERIALIZATION
# =============================================================================


def save_result(scored: ScoredDebate, output_dir: Path) -> Path:
    """Save scored debate to JSON with full scoring pipeline data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"debate_{scored.result.task_id}_{ts}.json"

    data = {
        "task_id": scored.result.task_id,
        "task_category": scored.task.category.value,
        "task_difficulty": scored.task.difficulty.value,
        "proposer_model": scored.result.proposer_model,
        "opponent_model": scored.result.opponent_model,
        "judge_model": scored.result.judge_model,
        "winner": scored.result.winner,
        "crux": scored.result.crux,
        "pre_mortem": scored.result.pre_mortem,
        "discriminative_power": scored.result.discriminative_power,
        "judge_scores": scored.result.scores,
        "num_turns": scored.result.num_turns,
        "total_tokens": scored.result.total_tokens,
        "total_latency_ms": scored.result.total_latency_ms,
        "turns": [
            {
                "turn_number": t.turn_number,
                "role": t.role.value,
                "model": t.model,
                "provider": t.provider,
                "content": t.content,
                "tokens_used": t.tokens_used,
                "thinking_tokens": t.thinking_tokens,
                "latency_ms": t.latency_ms,
                "metadata": t.metadata,
            }
            for t in scored.result.turns
        ],
        "timestamp": scored.result.timestamp.isoformat(),
    }

    if scored.scoring:
        s = scored.scoring
        data["scoring"] = {
            "rubric": {
                "dimensions": s.rubric.dimensions,
                "hard_fails": s.rubric.hard_fails,
                "reasoning": s.rubric.reasoning,
                "weighted_total": s.rubric.weighted_total,
                "is_hard_fail": s.rubric.is_hard_fail,
            },
            "cost": {
                "token_cost_usd": s.cost.token_cost_usd,
                "turn_cost_usd": s.cost.turn_cost_usd,
                "clarification_cost_usd": s.cost.clarification_cost_usd,
                "escalation_cost_usd": s.cost.escalation_cost_usd,
                "error_cost_usd": s.cost.error_cost_usd,
                "total_cost_usd": s.cost.total_cost_usd,
                "input_tokens": s.cost.input_tokens,
                "output_tokens": s.cost.output_tokens,
                "thinking_tokens": s.cost.thinking_tokens,
            },
            "reward": {
                "quality_score": s.reward.quality_score,
                "operational_cost": s.reward.operational_cost,
                "safety_penalty": s.reward.safety_penalty,
                "total_reward": s.reward.total_reward,
                "hard_fail": s.reward.hard_fail,
            },
        }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved: {filepath}")
    return filepath


def save_report(report: SuiteReport, output_dir: Path) -> Path:
    """Save aggregated suite report as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"suite_report_{ts}.json"

    data = {
        "summary": {
            "total_debates": len(report.debates),
            "succeeded": len(report.succeeded),
            "failed": len(report.failed),
            "success_rate": report.success_rate,
        },
        "model_performance": {
            model: {
                "role": perf.role,
                "debates": perf.debates,
                "wins": perf.wins,
                "draws": perf.draws,
                "losses": perf.losses,
                "win_rate": perf.win_rate,
                "avg_quality": perf.avg_quality,
                "avg_reward": perf.avg_reward,
                "avg_cost_usd": perf.avg_cost_usd,
                "total_tokens": perf.total_tokens,
                "total_thinking_tokens": perf.total_thinking_tokens,
            }
            for model, perf in report.model_performance.items()
        },
        "category_stats": report.category_stats,
        "timestamp": report.timestamp.isoformat(),
        "debate_ids": [d.result.task_id for d in report.debates],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Suite report: {filepath}")
    return filepath


# =============================================================================
# CLI
# =============================================================================


def _resolve_tasks(
    task_id: str | None,
    suite: bool,
    categories: list[str] | None,
    max_tasks: int | None,
) -> list[ArenaTask]:
    """Resolve CLI arguments into a concrete task list."""
    task_map = {t.id: t for t in SEED_TASKS}

    if task_id:
        if task_id not in task_map:
            print(f"Unknown task: {task_id}")
            print(f"Available: {', '.join(sorted(task_map))}")
            sys.exit(1)
        return [task_map[task_id]]

    if not suite:
        print("Specify --task <id> or --suite")
        print(f"\nAvailable tasks ({len(SEED_TASKS)}):")
        for t in SEED_TASKS:
            print(f"  {t.id:30s}  [{t.category.value}]")
        sys.exit(1)

    tasks = list(SEED_TASKS)

    if categories:
        valid = {c.value for c in TaskCategory}
        for cat in categories:
            if cat not in valid:
                print(f"Unknown category: {cat}")
                print(f"Available: {', '.join(sorted(valid))}")
                sys.exit(1)
        tasks = [t for t in tasks if t.category.value in categories]

    if max_tasks and max_tasks < len(tasks):
        tasks = tasks[:max_tasks]

    return tasks


def main():
    parser = argparse.ArgumentParser(
        description="ARENA Debate Runner — cross-provider adversarial evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s --task crux_01_acquisition\n"
            "  %(prog)s --suite --categories crux_identification adversarial_pressure\n"
            "  %(prog)s --suite --proposer gpt4o --opponent claude --max-tasks 5\n"
            "  %(prog)s --task adv_05_narrative --no-rubric --rounds 2\n"
            "  %(prog)s --suite --dry-run"
        ),
    )

    # Task selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--task", type=str, help="Single task ID to run")
    group.add_argument("--suite", action="store_true", help="Run full task suite")

    # Model selection
    presets = sorted(MODEL_PRESETS)
    parser.add_argument("--proposer", default="claude", choices=presets)
    parser.add_argument("--opponent", default="gemini", choices=presets)
    parser.add_argument("--judge", default=DEFAULT_JUDGE, choices=presets)

    # Configuration
    parser.add_argument("--rounds", type=int, default=3, help="Debate rounds")
    parser.add_argument(
        "--no-rubric", action="store_true",
        help="Skip scoring pipeline entirely",
    )
    parser.add_argument(
        "--heuristic", action="store_true",
        help="Use fast heuristic scoring (no extra LLM call)",
    )
    parser.add_argument("--categories", nargs="+", help="Filter suite by category")
    parser.add_argument("--max-tasks", type=int, help="Cap number of tasks")
    parser.add_argument("--output-dir", default="data/arena_results")
    parser.add_argument("--dry-run", action="store_true", help="Show plan, don't execute")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    tasks = _resolve_tasks(args.task, args.suite, args.categories, args.max_tasks)

    # --- Dry run ---
    if args.dry_run:
        scoring_mode = (
            "heuristic" if args.heuristic
            else "none" if args.no_rubric
            else "llm-judge"
        )
        print(f"\nDry run — {len(tasks)} task(s):")
        print(f"  Proposer : {MODEL_PRESETS[args.proposer].model}")
        print(f"  Opponent : {MODEL_PRESETS[args.opponent].model}")
        print(f"  Judge    : {MODEL_PRESETS[args.judge].model}")
        print(f"  Rounds   : {args.rounds}")
        print(f"  Scoring  : {scoring_mode}")
        print()
        for i, t in enumerate(tasks, 1):
            print(f"  {i:2d}. [{t.category.value}] {t.id}")
            q = t.question
            print(f"      {q[:65]}{'...' if len(q) > 65 else ''}")
        return

    # --- Execute ---
    config = DebateConfig(max_rounds=args.rounds)
    output_dir = Path(args.output_dir)
    do_score = not args.no_rubric

    if args.suite or len(tasks) > 1:
        report = run_suite(
            tasks=tasks,
            proposer_key=args.proposer,
            opponent_key=args.opponent,
            judge_key=args.judge,
            config=config,
            score=do_score,
            use_heuristic=args.heuristic,
        )
        for scored in report.succeeded:
            save_result(scored, output_dir)
        report_path = save_report(report, output_dir)
        print(f"\nSuite report: {report_path}")
    else:
        scored = run_debate(
            task=tasks[0],
            proposer_key=args.proposer,
            opponent_key=args.opponent,
            judge_key=args.judge,
            config=config,
            score=do_score,
            use_heuristic=args.heuristic,
        )
        if scored.succeeded:
            filepath = save_result(scored, output_dir)
            print(f"\nSaved: {filepath}")


if __name__ == "__main__":
    main()
