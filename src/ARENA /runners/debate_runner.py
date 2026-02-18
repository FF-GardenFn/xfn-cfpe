"""Debate runner: execute debates across seed tasks and model pairs.

Usage:
    python -m ARENA.runners.debate_runner --task crux_01_acquisition
    python -m ARENA.runners.debate_runner --all-tasks
    python -m ARENA.runners.debate_runner --task adv_05_narrative --proposer claude --opponent gemini
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ARENA.protocols.debate import DebateProtocol, DebateConfig, DebateResult, ModelConfig
from ARENA.scoring.cost_model import CostModel
from ARENA.scoring.reward import CompositeReward
from ARENA.tasks.seed_tasks import SEED_TASKS, ArenaTask
# from get_responses.catalogs.models import MODELS, get_models...

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL PRESETS
# =============================================================================

MODEL_PRESETS: dict[str, ModelConfig] = {
    "claude": ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514"),
    "claude-opus": ModelConfig(provider="anthropic", model="claude-opus-4-5-20251101"),
    "claude-haiku": ModelConfig(provider="anthropic", model="claude-haiku-4-5-20251001"),
    "gemini": ModelConfig(provider="google", model="gemini-2.0-flash"),
    "gemini-pro": ModelConfig(provider="google", model="gemini-1.5-pro"),
    "gpt4o": ModelConfig(provider="openai", model="gpt-4o"),
    "grok": ModelConfig(provider="xai", model="grok-2-1212"),
}

DEFAULT_JUDGE = "claude-opus"


# =============================================================================
# RUNNER
# =============================================================================

def run_debate(
    task: ArenaTask,
    proposer_key: str = "claude",
    opponent_key: str = "gemini",
    judge_key: str = DEFAULT_JUDGE,
    config: DebateConfig | None = None,
) -> DebateResult:
    """Run a single debate.

    Args:
        task: The task to debate.
        proposer_key: Key into MODEL_PRESETS for proposer.
        opponent_key: Key into MODEL_PRESETS for opponent.
        judge_key: Key into MODEL_PRESETS for judge.
        config: Debate configuration.

    Returns:
        DebateResult with transcript, scores, and analysis.
    """
    proposer = MODEL_PRESETS[proposer_key]
    opponent = MODEL_PRESETS[opponent_key]
    judge = MODEL_PRESETS[judge_key]

    protocol = DebateProtocol(
        proposer=proposer,
        opponent=opponent,
        judge=judge,
        config=config or DebateConfig(),
    )

    print(f"\n{'='*70}")
    print(f"ARENA DEBATE: {task.id}")
    print(f"{'='*70}")
    print(f"Question: {task.question[:80]}...")
    print(f"Proposer: {proposer.model}")
    print(f"Opponent: {opponent.model}")
    print(f"Judge: {judge.model}")
    print(f"{'='*70}\n")

    result = protocol.run(task)

    # Print summary
    print(f"\n--- RESULT ---")
    print(f"Winner: {result.winner}")
    print(f"Crux: {result.crux}")
    print(f"Pre-mortem: {result.pre_mortem}")
    print(f"Discriminative power: {result.discriminative_power}/10")
    print(f"Total turns: {result.num_turns}")
    print(f"Total tokens: {result.total_tokens}")

    if result.scores:
        print(f"\nScores:")
        for k, v in sorted(result.scores.items()):
            print(f"  {k}: {v}")

    return result


def save_result(result: DebateResult, output_dir: Path) -> Path:
    """Save debate result to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"debate_{result.task_id}_{timestamp}.json"

    data = {
        "task_id": result.task_id,
        "proposer_model": result.proposer_model,
        "opponent_model": result.opponent_model,
        "judge_model": result.judge_model,
        "winner": result.winner,
        "crux": result.crux,
        "pre_mortem": result.pre_mortem,
        "discriminative_power": result.discriminative_power,
        "scores": result.scores,
        "num_turns": result.num_turns,
        "total_tokens": result.total_tokens,
        "total_latency_ms": result.total_latency_ms,
        "turns": [
            {
                "turn_number": t.turn_number,
                "role": t.role.value,
                "model": t.model,
                "provider": t.provider,
                "content": t.content,
                "tokens_used": t.tokens_used,
                "latency_ms": t.latency_ms,
            }
            for t in result.turns
        ],
        "timestamp": result.timestamp.isoformat(),
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ARENA Debate Runner")
    parser.add_argument("--task", type=str, help="Task ID to run")
    parser.add_argument("--all-tasks", action="store_true", help="Run all seed tasks")
    parser.add_argument("--proposer", type=str, default="claude", choices=MODEL_PRESETS.keys())
    parser.add_argument("--opponent", type=str, default="gemini", choices=MODEL_PRESETS.keys())
    parser.add_argument("--judge", type=str, default=DEFAULT_JUDGE, choices=MODEL_PRESETS.keys())
    parser.add_argument("--rounds", type=int, default=3, help="Debate rounds")
    parser.add_argument("--output-dir", type=str, default="data/arena_results")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = DebateConfig(max_rounds=args.rounds)
    output_dir = Path(args.output_dir)

    task_map = {t.id: t for t in SEED_TASKS}

    if args.all_tasks:
        tasks = SEED_TASKS
    elif args.task:
        if args.task not in task_map:
            print(f"Unknown task: {args.task}")
            print(f"Available: {', '.join(task_map.keys())}")
            sys.exit(1)
        tasks = [task_map[args.task]]
    else:
        print("Specify --task <id> or --all-tasks")
        sys.exit(1)

    for task in tasks:
        result = run_debate(
            task=task,
            proposer_key=args.proposer,
            opponent_key=args.opponent,
            judge_key=args.judge,
            config=config,
        )
        filepath = save_result(result, output_dir)
        print(f"\nSaved to: {filepath}")


if __name__ == "__main__":
    main()
