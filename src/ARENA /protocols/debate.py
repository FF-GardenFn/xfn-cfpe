"""Debate protocol: cross-provider adversarial reasoning evaluation.

Two models alternate on the same task. Each sees the other's argument.
A judge model scores the debate using the 8-dimension rubric.

This produces:
- Adversarial test cases (opponent arguments that succeed become new eval tasks)
- Crux identification (what claims actually flip conclusions)
- Model separation (which models update on evidence vs. entrench)

Usage:
    debate = DebateProtocol(
        proposer=ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514"),
        opponent=ModelConfig(provider="google", model="gemini-2.0-flash"),
        judge=ModelConfig(provider="anthropic", model="claude-opus-4-5-20251101"),
    )
    result = debate.run(task)
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import Protocol, ProtocolResult, ProtocolTurn, Role

# Add parent paths for get_responses imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ModelConfig:
    """Configuration for a model participant."""
    provider: str  # "anthropic", "openai", "google", "xai"
    model: str     # Full model ID
    system_prompt: str | None = None
    enable_thinking: bool = False


@dataclass
class DebateConfig:
    """Configuration for a debate."""
    max_rounds: int = 3
    max_tokens_per_turn: int = 2000
    judge_rubric: str = "8-dimension"  # or "binary", "custom"
    record_thinking: bool = True
    allow_concession: bool = True


# =============================================================================
# PROMPTS
# =============================================================================

PROPOSER_SYSTEM = """You are participating in a structured debate. Your role is PROPOSER.

You will be given a task and must argue for your position. In subsequent rounds,
you will see the opponent's counter-arguments and must respond to them directly.

Rules:
- Address the opponent's strongest points, not their weakest
- Identify cruxes: claims that, if proven wrong, would change your conclusion
- You may revise your position if the opponent's evidence is compelling
- State your confidence level (0-100%) and what would change it
- Be specific and concrete, not abstract"""

OPPONENT_SYSTEM = """You are participating in a structured debate. Your role is OPPONENT.

You will see the proposer's argument and must challenge it. Your goal is NOT to
"win" but to find genuine weaknesses, missing assumptions, and blind spots.

Rules:
- Attack the strongest version of the argument, not a strawman
- Identify specific claims that are unsupported or wrong
- Propose concrete counter-evidence or counter-examples
- State what would convince you the proposer is right
- If a point is genuinely strong, acknowledge it"""

JUDGE_SYSTEM = """You are judging a structured debate. Score BOTH participants on these dimensions:

1. **Crux identification** (0-10): Did they identify the decision-critical factors?
2. **Evidence quality** (0-10): Specific, verifiable claims vs. vague assertions?
3. **Position updates** (0-10): Did they update on evidence or just entrench?
4. **Epistemic honesty** (0-10): Accurate confidence, acknowledged uncertainty?
5. **Argument structure** (0-10): Coherent reasoning, no contradictions?

Also identify:
- The **crux** of the debate (the single claim that, if resolved, determines the answer)
- **Winner** (or draw) with reasoning
- **Pre-mortem**: If the winning position fails, the most likely cause is...

Respond with ONLY valid JSON:
{
    "proposer_scores": {"crux": N, "evidence": N, "updates": N, "honesty": N, "structure": N},
    "opponent_scores": {"crux": N, "evidence": N, "updates": N, "honesty": N, "structure": N},
    "crux": "The key claim that determines the answer",
    "winner": "proposer" | "opponent" | "draw",
    "winner_reasoning": "Why",
    "pre_mortem": "If the winning position fails, because...",
    "discriminative_power": 0-10
}"""


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class DebateResult(ProtocolResult):
    """Extended result for debate protocol."""
    proposer_model: str = ""
    opponent_model: str = ""
    judge_model: str = ""
    crux: str = ""
    winner: str = ""
    pre_mortem: str = ""
    discriminative_power: float = 0.0
    position_changes: int = 0


# =============================================================================
# DEBATE PROTOCOL
# =============================================================================

class DebateProtocol(Protocol):
    """Cross-provider adversarial debate evaluation.

    Executes a structured debate between two models with judge scoring.
    Builds on the existing get_responses infrastructure for provider access.
    """

    def __init__(
        self,
        proposer: ModelConfig,
        opponent: ModelConfig,
        judge: ModelConfig,
        config: DebateConfig | None = None,
    ):
        self.proposer = proposer
        self.opponent = opponent
        self.judge = judge
        self.config = config or DebateConfig()
        self._processor = None  # Lazy init

    def _get_processor(self):
        """Lazy-init the processor from get_responses."""
        if self._processor is None:
            from get_responses.processor import Processor
            self._processor = Processor()
        return self._processor

    def _call_model(
        self,
        config: ModelConfig,
        prompt: str,
        role: Role,
    ) -> ProtocolTurn:
        """Make a single model call via the get_responses infrastructure.

        Args:
            config: Model configuration.
            prompt: The prompt to send.
            role: The role of this participant.

        Returns:
            ProtocolTurn with response and metrics.
        """
        processor = self._get_processor()

        response = processor.run_single(
            prompt=prompt,
            system_prompt=config.system_prompt,
            system_prompt_name=f"arena_{role.value}",
            model=config.model,
            enable_thinking=config.enable_thinking,
            max_tokens=self.config.max_tokens_per_turn,
        )

        return ProtocolTurn(
            turn_number=0,  # Set by caller
            role=role,
            model=config.model,
            provider=config.provider,
            content=response.answer,
            tokens_used=response.usage.total_tokens,
            thinking_tokens=getattr(response.usage, 'thinking_tokens', 0) or 0,
            latency_ms=response.latency_ms,
        )

    def run(self, task: Any, **kwargs) -> DebateResult:
        """Execute a structured debate.

        Args:
            task: ArenaTask with question, context, and metadata.

        Returns:
            DebateResult with full transcript, scores, and analysis.
        """
        turns: list[ProtocolTurn] = []
        debate_history = []
        turn_counter = 0

        # Set system prompts if not already configured
        if self.proposer.system_prompt is None:
            self.proposer.system_prompt = PROPOSER_SYSTEM
        if self.opponent.system_prompt is None:
            self.opponent.system_prompt = OPPONENT_SYSTEM

        logger.info(f"Starting debate: {task.id}")
        logger.info(f"  Proposer: {self.proposer.model}")
        logger.info(f"  Opponent: {self.opponent.model}")
        logger.info(f"  Judge: {self.judge.model}")

        for round_num in range(1, self.config.max_rounds + 1):
            logger.info(f"  Round {round_num}/{self.config.max_rounds}")

            # --- Proposer turn ---
            if round_num == 1:
                proposer_prompt = (
                    f"Task: {task.question}\n\n"
                    f"Context: {task.context}\n\n"
                    f"Present your position."
                )
            else:
                last_opponent = debate_history[-1]
                proposer_prompt = (
                    f"Task: {task.question}\n\n"
                    f"Your previous argument:\n{debate_history[-2]}\n\n"
                    f"Opponent's counter-argument:\n{last_opponent}\n\n"
                    f"Respond to the opponent's points. You may revise your position."
                )

            turn_counter += 1
            proposer_turn = self._call_model(
                self.proposer, proposer_prompt, Role.PROPOSER
            )
            proposer_turn.turn_number = turn_counter
            turns.append(proposer_turn)
            debate_history.append(proposer_turn.content)

            # --- Opponent turn ---
            if round_num == 1:
                opponent_prompt = (
                    f"Task: {task.question}\n\n"
                    f"Context: {task.context}\n\n"
                    f"The proposer argues:\n{proposer_turn.content}\n\n"
                    f"Challenge this argument."
                )
            else:
                opponent_prompt = (
                    f"Task: {task.question}\n\n"
                    f"Debate so far:\n"
                )
                for i, entry in enumerate(debate_history):
                    role_label = "Proposer" if i % 2 == 0 else "Opponent"
                    opponent_prompt += f"\n[{role_label}]: {entry}\n"
                opponent_prompt += "\nRespond to the proposer's latest argument."

            turn_counter += 1
            opponent_turn = self._call_model(
                self.opponent, opponent_prompt, Role.OPPONENT
            )
            opponent_turn.turn_number = turn_counter
            turns.append(opponent_turn)
            debate_history.append(opponent_turn.content)

        # --- Judge scoring ---
        judge_prompt = f"Task: {task.question}\n\nFull debate transcript:\n"
        for i, entry in enumerate(debate_history):
            role_label = "Proposer" if i % 2 == 0 else "Opponent"
            judge_prompt += f"\n--- {role_label} (Round {i // 2 + 1}) ---\n{entry}\n"
        judge_prompt += "\nScore this debate."

        if self.judge.system_prompt is None:
            self.judge.system_prompt = JUDGE_SYSTEM

        turn_counter += 1
        judge_turn = self._call_model(self.judge, judge_prompt, Role.JUDGE)
        judge_turn.turn_number = turn_counter
        turns.append(judge_turn)

        # Parse judge scores
        scores, crux, winner, pre_mortem, disc_power = self._parse_judge(
            judge_turn.content
        )

        return DebateResult(
            protocol_name="debate",
            task_id=task.id,
            turns=turns,
            scores=scores,
            proposer_model=self.proposer.model,
            opponent_model=self.opponent.model,
            judge_model=self.judge.model,
            crux=crux,
            winner=winner,
            pre_mortem=pre_mortem,
            discriminative_power=disc_power,
        )

    def _parse_judge(
        self, judge_content: str
    ) -> tuple[dict[str, float], str, str, str, float]:
        """Parse judge response into structured scores.

        Returns:
            (scores_dict, crux, winner, pre_mortem, discriminative_power)
        """
        try:
            # Handle markdown code blocks
            content = judge_content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        json_lines.append(line)
                content = "\n".join(json_lines)

            data = json.loads(content)

            # Flatten scores
            scores = {}
            for prefix, sub_scores in [
                ("proposer", data.get("proposer_scores", {})),
                ("opponent", data.get("opponent_scores", {})),
            ]:
                for dim, val in sub_scores.items():
                    scores[f"{prefix}_{dim}"] = float(val)

            return (
                scores,
                data.get("crux", ""),
                data.get("winner", "draw"),
                data.get("pre_mortem", ""),
                float(data.get("discriminative_power", 0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse judge response: {e}")
            return {}, "", "draw", "", 0.0

    def score(self, result: ProtocolResult) -> dict[str, float]:
        """Score an existing debate result."""
        return result.scores
