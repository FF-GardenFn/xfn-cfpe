"""Prompt router: contextual bandit for prompt variant selection.

Different prompts win on different task types. The router learns which
prompt variant to deploy based on task features, optimizing:

    Quality - lambda * Cost - mu * SafetyRisk

Variants:
    - baseline: fast default, no system prompt
    - dialectica: deep reasoning with O-CoV (complex/ambiguous tasks)
    - rigor: anti-hallucination, citation-heavy (factual claims)
    - structured: extraction tasks (JSON, tables, structured output)
    - agent: tool-use tasks (multi-step with tool calls)

Training data comes from logged rollouts:
    (task_features, chosen_prompt, reward_breakdown)

Implementation: contextual bandit with Thompson sampling.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT VARIANTS
# =============================================================================

class PromptVariant(str, Enum):
    """Available prompt variants."""
    BASELINE = "baseline"
    DIALECTICA = "dialectica"
    RIGOR = "rigor"
    STRUCTURED = "structured"
    AGENT = "agent"


@dataclass
class TaskFeatures:
    """Features extracted from a task for routing decisions."""
    query_length: int = 0
    has_code: bool = False
    has_numbers: bool = False
    question_type: str = "open"  # "open", "factual", "extraction", "tool_use"
    ambiguity_score: float = 0.5  # 0 = clear, 1 = highly ambiguous
    domain: str = "general"
    requires_reasoning: bool = True
    multi_step: bool = False

    def to_vector(self) -> np.ndarray:
        """Convert to feature vector for bandit."""
        return np.array([
            self.query_length / 1000,  # Normalize
            float(self.has_code),
            float(self.has_numbers),
            {"open": 0, "factual": 1, "extraction": 2, "tool_use": 3}.get(self.question_type, 0) / 3,
            self.ambiguity_score,
            float(self.requires_reasoning),
            float(self.multi_step),
        ])


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    variant: PromptVariant
    confidence: float  # How confident the router is in this choice
    reasoning: str     # Why this variant was chosen
    features: TaskFeatures | None = None


# =============================================================================
# LOGGED ROLLOUT
# =============================================================================

@dataclass
class Rollout:
    """A logged rollout for offline training."""
    task_features: TaskFeatures
    chosen_variant: PromptVariant
    reward: float  # From CompositeReward.compute()
    reward_breakdown: dict[str, float] = field(default_factory=dict)
    timestamp: str = ""


# =============================================================================
# PROMPT ROUTER
# =============================================================================

class PromptRouter:
    """Contextual bandit prompt router with Thompson sampling.

    Learns which prompt variant works best for different task types
    by maintaining Beta distribution parameters for each (feature_bin, variant) pair.

    Phases:
    1. Rule-based: Deterministic routing based on task features (current)
    2. Epsilon-greedy: Mostly rule-based, random exploration (next)
    3. Thompson sampling: Bayesian exploration-exploitation (target)
    """

    def __init__(
        self,
        exploration_rate: float = 0.1,
        rollout_log_path: Path | None = None,
    ):
        self.exploration_rate = exploration_rate
        self.rollout_log_path = rollout_log_path or Path("data/rollouts.jsonl")

        # Beta distribution parameters per variant
        # alpha = successes + 1, beta = failures + 1 (uniform prior)
        self._alpha: dict[PromptVariant, float] = {v: 1.0 for v in PromptVariant}
        self._beta: dict[PromptVariant, float] = {v: 1.0 for v in PromptVariant}

        # Per-feature-bin parameters (for contextual version)
        self._context_alpha: dict[str, dict[PromptVariant, float]] = {}
        self._context_beta: dict[str, dict[PromptVariant, float]] = {}

        self._rollouts: list[Rollout] = []

    # -------------------------------------------------------------------------
    # Phase 1: Rule-based routing
    # -------------------------------------------------------------------------

    def route_rules(self, features: TaskFeatures) -> RoutingDecision:
        """Deterministic routing based on task features.

        This is the baseline — always available as fallback.
        """
        # Tool-use tasks → agent variant
        if features.multi_step or features.question_type == "tool_use":
            return RoutingDecision(
                variant=PromptVariant.AGENT,
                confidence=0.8,
                reasoning="Multi-step or tool-use task detected",
                features=features,
            )

        # Extraction tasks → structured variant
        if features.question_type == "extraction":
            return RoutingDecision(
                variant=PromptVariant.STRUCTURED,
                confidence=0.9,
                reasoning="Extraction task detected",
                features=features,
            )

        # Factual with numbers → rigor variant
        if features.question_type == "factual" and features.has_numbers:
            return RoutingDecision(
                variant=PromptVariant.RIGOR,
                confidence=0.7,
                reasoning="Factual task with numerical claims",
                features=features,
            )

        # High ambiguity + requires reasoning → dialectica
        if features.ambiguity_score > 0.6 and features.requires_reasoning:
            return RoutingDecision(
                variant=PromptVariant.DIALECTICA,
                confidence=0.8,
                reasoning="High ambiguity + reasoning required → deep dialectic",
                features=features,
            )

        # Simple/clear → baseline
        if features.ambiguity_score < 0.3 and not features.requires_reasoning:
            return RoutingDecision(
                variant=PromptVariant.BASELINE,
                confidence=0.9,
                reasoning="Simple query, bypass deep reasoning",
                features=features,
            )

        # Default: dialectica for anything uncertain
        return RoutingDecision(
            variant=PromptVariant.DIALECTICA,
            confidence=0.5,
            reasoning="Default to dialectica for uncertain tasks",
            features=features,
        )

    # -------------------------------------------------------------------------
    # Phase 2: Epsilon-greedy
    # -------------------------------------------------------------------------

    def route_epsilon_greedy(self, features: TaskFeatures) -> RoutingDecision:
        """Epsilon-greedy: mostly rule-based, occasionally random."""
        if random.random() < self.exploration_rate:
            variant = random.choice(list(PromptVariant))
            return RoutingDecision(
                variant=variant,
                confidence=0.0,  # Exploration
                reasoning=f"Exploration (epsilon={self.exploration_rate})",
                features=features,
            )
        return self.route_rules(features)

    # -------------------------------------------------------------------------
    # Phase 3: Thompson sampling
    # -------------------------------------------------------------------------

    def route_thompson(self, features: TaskFeatures) -> RoutingDecision:
        """Thompson sampling: sample from posterior Beta distributions."""
        samples = {}
        for variant in PromptVariant:
            alpha = self._alpha[variant]
            beta = self._beta[variant]
            samples[variant] = np.random.beta(alpha, beta)

        best_variant = max(samples, key=lambda v: samples[v])

        return RoutingDecision(
            variant=best_variant,
            confidence=float(samples[best_variant]),
            reasoning=f"Thompson sampling (sampled {samples[best_variant]:.3f})",
            features=features,
        )

    # -------------------------------------------------------------------------
    # Unified interface
    # -------------------------------------------------------------------------

    def route(
        self,
        features: TaskFeatures,
        method: str = "rules",
    ) -> RoutingDecision:
        """Route a task to a prompt variant.

        Args:
            features: Task features.
            method: "rules", "epsilon_greedy", or "thompson".

        Returns:
            RoutingDecision with chosen variant and reasoning.
        """
        if method == "rules":
            return self.route_rules(features)
        elif method == "epsilon_greedy":
            return self.route_epsilon_greedy(features)
        elif method == "thompson":
            return self.route_thompson(features)
        else:
            raise ValueError(f"Unknown routing method: {method}")

    # -------------------------------------------------------------------------
    # Learning
    # -------------------------------------------------------------------------

    def update(self, variant: PromptVariant, reward: float) -> None:
        """Update posterior after observing a reward.

        Args:
            variant: The variant that was used.
            reward: The observed reward (higher = better).
        """
        # Convert reward to binary success/failure for Beta update
        # Threshold at 0 (positive reward = success)
        if reward > 0:
            self._alpha[variant] += 1.0
        else:
            self._beta[variant] += 1.0

    def log_rollout(self, rollout: Rollout) -> None:
        """Log a rollout for offline analysis and training."""
        self._rollouts.append(rollout)

        # Persist to JSONL
        self.rollout_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rollout_log_path, "a") as f:
            f.write(json.dumps({
                "features": rollout.task_features.__dict__,
                "variant": rollout.chosen_variant.value,
                "reward": rollout.reward,
                "reward_breakdown": rollout.reward_breakdown,
                "timestamp": rollout.timestamp,
            }) + "\n")

    def stats(self) -> dict[str, Any]:
        """Return current router statistics."""
        return {
            variant.value: {
                "alpha": self._alpha[variant],
                "beta": self._beta[variant],
                "mean": self._alpha[variant] / (self._alpha[variant] + self._beta[variant]),
                "samples": int(self._alpha[variant] + self._beta[variant] - 2),
            }
            for variant in PromptVariant
        }
