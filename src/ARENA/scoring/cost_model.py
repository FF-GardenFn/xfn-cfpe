"""Operational cost model from /evaluation/benchmarks/equ.md.

Measures total cost of a model interaction — not just tokens, but the full
user experience: turns, clarifications, escalations, and error correction.

A model that resolves in 1 turn at 2,000 tokens beats a model that resolves
in 4 turns at 500 tokens each — even though the second used the same total.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# PRICING (from /src/get_responses/catalogs/models.py)
# =============================================================================

# Per-million-token pricing as of Jan 2026
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic (input, output per 1M tokens)
    "claude-haiku-4-5-20251001": (0.25, 1.25),
    "claude-sonnet-4-20250514": (0.30, 1.50),
    "claude-4-5-sonnet-20260115": (3.00, 15.00),
    "claude-opus-4-5-20251101": (5.00, 25.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    # Google
    "gemini-2.0-flash": (0.08, 0.30),
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-1.5-pro": (2.50, 10.00),
    # xAI
    "grok-2-1212": (2.00, 10.00),
}


# =============================================================================
# COST COEFFICIENTS (configurable, calibration ongoing)
# =============================================================================

@dataclass
class CostCoefficients:
    """Coefficients for the operational cost equation.

    These need calibration from user studies or proxy metrics.
    See /evaluation/benchmarks/equ.md for calibration TODOs.
    """
    user_time_per_turn_usd: float = 0.50  # ~30s at $60/hr
    frustration_coefficient: float = 1.5   # Multiplier on clarification cost
    correction_cost_usd: float = 2.00      # Cost of fixing an error

    # Task-adjusted variant
    hourly_rate_usd: float = 60.0  # Default; override per task type


# =============================================================================
# COST BREAKDOWN
# =============================================================================

@dataclass
class CostBreakdown:
    """Itemized cost breakdown for a model interaction."""
    token_cost_usd: float = 0.0
    turn_cost_usd: float = 0.0
    clarification_cost_usd: float = 0.0
    escalation_cost_usd: float = 0.0
    error_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    # Raw inputs (for analysis)
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    num_turns: int = 0
    num_clarifications: int = 0
    num_escalations: int = 0
    error_rate: float = 0.0
    model: str = ""

    def __repr__(self) -> str:
        return (
            f"CostBreakdown(total=${self.total_cost_usd:.4f}, "
            f"tokens=${self.token_cost_usd:.4f}, "
            f"turns=${self.turn_cost_usd:.4f}, "
            f"clarifications=${self.clarification_cost_usd:.4f}, "
            f"errors=${self.error_cost_usd:.4f})"
        )


# =============================================================================
# COST MODEL
# =============================================================================

class CostModel:
    """Implements the operational cost equation.

    Total Cost = (Tokens x Price)
               + (Turns x User Time)
               + (Clarifications x Frustration Coefficient)
               + (Escalations x Model Price Delta)
               + (Error Rate x Correction Cost)
    """

    def __init__(self, coefficients: CostCoefficients | None = None):
        self.coefficients = coefficients or CostCoefficients()

    def token_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
    ) -> float:
        """Calculate raw token cost in USD."""
        pricing = MODEL_PRICING.get(model)
        if pricing is None:
            # Fallback to Sonnet pricing if unknown model
            pricing = (0.30, 1.50)

        input_price, output_price = pricing
        cost = (input_tokens * input_price / 1_000_000) + (
            output_tokens * output_price / 1_000_000
        )
        # Thinking tokens charged at input rate for most providers
        cost += thinking_tokens * input_price / 1_000_000
        return cost

    def escalation_cost(self, from_model: str, to_model: str, tokens: int) -> float:
        """Cost delta of escalating from cheaper to more expensive model."""
        from_pricing = MODEL_PRICING.get(from_model, (0.30, 1.50))
        to_pricing = MODEL_PRICING.get(to_model, (5.00, 25.00))
        delta_per_token = (to_pricing[1] - from_pricing[1]) / 1_000_000
        return max(0, delta_per_token * tokens)

    def compute(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
        num_turns: int = 1,
        num_clarifications: int = 0,
        num_escalations: int = 0,
        escalation_model: str | None = None,
        escalation_tokens: int = 0,
        error_rate: float = 0.0,
    ) -> CostBreakdown:
        """Compute full operational cost.

        Args:
            model: Model ID used.
            input_tokens: Total input tokens.
            output_tokens: Total output tokens.
            thinking_tokens: Extended thinking tokens.
            num_turns: Number of conversation turns.
            num_clarifications: Turns that were clarification requests.
            num_escalations: Times model was escalated to a more expensive one.
            escalation_model: Model escalated to (for price delta).
            escalation_tokens: Tokens used in escalation calls.
            error_rate: Fraction of responses requiring correction (0.0-1.0).

        Returns:
            CostBreakdown with itemized and total cost.
        """
        c = self.coefficients

        tok_cost = self.token_cost(model, input_tokens, output_tokens, thinking_tokens)
        turn_cost = num_turns * c.user_time_per_turn_usd
        clar_cost = num_clarifications * c.user_time_per_turn_usd * c.frustration_coefficient
        esc_cost = (
            self.escalation_cost(model, escalation_model or model, escalation_tokens)
            * num_escalations
        )
        err_cost = error_rate * c.correction_cost_usd

        total = tok_cost + turn_cost + clar_cost + esc_cost + err_cost

        return CostBreakdown(
            token_cost_usd=tok_cost,
            turn_cost_usd=turn_cost,
            clarification_cost_usd=clar_cost,
            escalation_cost_usd=esc_cost,
            error_cost_usd=err_cost,
            total_cost_usd=total,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            num_turns=num_turns,
            num_clarifications=num_clarifications,
            num_escalations=num_escalations,
            error_rate=error_rate,
            model=model,
        )

    def compare(
        self, breakdown_a: CostBreakdown, breakdown_b: CostBreakdown
    ) -> dict[str, float]:
        """Compare two cost breakdowns.

        Returns dict with deltas (positive = B is more expensive).
        """
        return {
            "total_delta": breakdown_b.total_cost_usd - breakdown_a.total_cost_usd,
            "token_delta": breakdown_b.token_cost_usd - breakdown_a.token_cost_usd,
            "turn_delta": breakdown_b.turn_cost_usd - breakdown_a.turn_cost_usd,
            "clarification_delta": (
                breakdown_b.clarification_cost_usd - breakdown_a.clarification_cost_usd
            ),
            "a_total": breakdown_a.total_cost_usd,
            "b_total": breakdown_b.total_cost_usd,
            "savings_pct": (
                (breakdown_a.total_cost_usd - breakdown_b.total_cost_usd)
                / breakdown_a.total_cost_usd
                * 100
                if breakdown_a.total_cost_usd > 0
                else 0
            ),
        }
