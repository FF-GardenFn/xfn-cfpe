#!/usr/bin/env python3
"""Tests for the coupled-objective spirit term wired into ARENA's reward.

Surface B of the three-surface program: the coupled-objective hidden readout H
(CAI/kernel/spirit_scorer.py) becomes the live gamma_spirit term in

    R = alpha*quality - beta*cost - gamma*safety_penalty - gamma_spirit*H

INFRASTRUCTURE ONLY. This proves the plumbing composes and is backward
compatible; it does NOT demonstrate the coupling is causal (that optimizing the
visible objective moves H) -- that requires the live-model chooser, which is
blocked on transport + compute.

Invariants asserted (the coordinator's Surface B conditions):
  - backward compat: at spirit_H == 0 the reward equals the no-H path EXACTLY,
    in both the normal and the hard-fail branch. (The byte-identical before/after
    proof for spirit_H OMITTED is done separately against a golden snapshot.)
  - boundary: at spirit_H == 1 the spirit penalty equals gamma_spirit EXACTLY.
  - monotonic: total_reward strictly decreases as H rises.
  - linearity + clamp: total = base - gamma_spirit * clamp(H, 0, 1).

Run:  python src/ARENA/scoring/test_coupled_reward.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # -> src/

from ARENA.scoring.reward import CompositeReward, RewardConfig  # noqa: E402
from ARENA.scoring.cost_model import CostBreakdown  # noqa: E402

CR = CompositeReward(RewardConfig())
GS = RewardConfig().gamma_spirit  # 2.0

# (name, dimension_scores, cost_usd, violations, hard_fails) -- includes a
# hard-fail case so the boundary is checked in BOTH reward branches.
CASES = [
    ("clean_mid", {"crux": 7, "oscillation": 5}, 0.80, [], []),
    ("with_violation", {"crux": 8}, 0.50, ["tool_violation"], []),
    ("hard_fail", {"crux": 9}, 0.50, [], ["factual_fabrication"]),
]


def _reward(dims, cost, viols, hf, spirit_H=None):
    return CR.compute(dims, CostBreakdown(total_cost_usd=cost), viols, hf,
                      spirit_H=spirit_H)


def run() -> int:
    checks: list[tuple[str, bool]] = []

    for name, dims, cost, viols, hf in CASES:
        base = _reward(dims, cost, viols, hf)                    # no-H path
        h0 = _reward(dims, cost, viols, hf, spirit_H=0.0)
        h1 = _reward(dims, cost, viols, hf, spirit_H=1.0)

        # backward compat: H == 0 identical to no-H path (exact), no contribution
        checks.append((f"[{name}] H=0 total == no-H total (exact)",
                       h0.total_reward == base.total_reward))
        checks.append((f"[{name}] H=0 spirit_penalty == 0 (exact)",
                       h0.spirit_penalty == 0.0))

        # boundary: at H == 1 the spirit penalty equals gamma_spirit exactly
        checks.append((f"[{name}] H=1 spirit_penalty == gamma_spirit (exact)",
                       h1.spirit_penalty == GS))
        checks.append((f"[{name}] H=1 lowers total by exactly gamma_spirit",
                       abs((base.total_reward - h1.total_reward) - GS) < 1e-9))

        # monotonic strictly decreasing in H
        hs = [0.0, 0.25, 0.5, 0.75, 1.0]
        totals = [_reward(dims, cost, viols, hf, spirit_H=h).total_reward for h in hs]
        checks.append((f"[{name}] total strictly decreasing in H",
                       all(a > b for a, b in zip(totals, totals[1:]))))

        # linearity: total == base - gamma_spirit * H (scaled right, not just monotone)
        lin = all(abs(_reward(dims, cost, viols, hf, spirit_H=h).total_reward
                      - (base.total_reward - GS * h)) < 1e-9 for h in hs)
        checks.append((f"[{name}] total == base - gamma_spirit*H (correct scale)", lin))

        # clamp: H>1 behaves as H=1, H<0 behaves as H=0
        checks.append((f"[{name}] H=1.5 clamps to H=1",
                       _reward(dims, cost, viols, hf, spirit_H=1.5).total_reward
                       == h1.total_reward))
        checks.append((f"[{name}] H=-0.3 clamps to H=0",
                       _reward(dims, cost, viols, hf, spirit_H=-0.3).total_reward
                       == h0.total_reward))

    print("ARENA coupled-objective spirit-term tests (Surface B)\n")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print(f"\nRESULT: {'PASS' if ok else 'FAIL'} ({sum(p for _, p in checks)}/{len(checks)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
