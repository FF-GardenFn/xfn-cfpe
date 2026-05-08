"""
Scheduling utilities driven by step count or wallclock fraction.

These ramp/gating functions produce time-varying scalars used to control:
  - QAT noise injection (ramp from 0 → 1 across a configurable window)
  - Auxiliary obfuscation losses (active in a windowed step/wallclock band)
  - Transformer logit gate (suppressed early to preserve a bigram headstart)

All functions accept either step-driven or wallclock-driven schedules; if
`max_wallclock_ms` is None or non-positive, schedules fall back to step-based
fractions. Wallclock-driven scheduling makes ramps invariant to per-iteration
wall time, useful when wallclock budget rather than iteration count bounds the
training run.

Extracted from `train_gpt.py` (Farhat).
"""

from __future__ import annotations


def wallclock_fraction(elapsed_ms: float, max_wallclock_ms: float | None) -> float | None:
    """Return elapsed/max as a fraction in [0, 1], or None if no max set."""
    if max_wallclock_ms is None or max_wallclock_ms <= 0.0:
        return None
    return min(max(elapsed_ms / max_wallclock_ms, 0.0), 1.0)


def aux_obf_scale(
    step: int,
    elapsed_ms: float,
    max_wallclock_ms: float | None,
    start_step: int,
    end_step: int,
    start_frac: float,
    end_frac: float,
    base_weight: float,
) -> float:
    """Auxiliary obfuscation-loss gate: active inside a step or wallclock window.

    Returns 1.0 when the schedule is in [start, end] and 0.0 otherwise. If
    `base_weight <= 0`, returns 0.0 unconditionally (loss is disabled).
    """
    if base_weight <= 0.0:
        return 0.0
    frac = wallclock_fraction(elapsed_ms, max_wallclock_ms)
    if frac is None:
        return 1.0 if start_step <= step <= end_step else 0.0
    return 1.0 if start_frac <= frac <= end_frac else 0.0


def qat_noise_scale(
    step: int,
    elapsed_ms: float,
    max_wallclock_ms: float | None,
    total_steps: int,
    start_frac: float,
    full_frac: float,
) -> float:
    """QAT noise ramp: 0 before start, linearly up to 1 by full_frac.

    Wallclock mode (preferred): start_frac and full_frac are wallclock fractions.
    Step mode (fallback): start_frac and full_frac scale total_steps to step indices.
    """
    frac = wallclock_fraction(elapsed_ms, max_wallclock_ms)
    if frac is None:
        ramp_start = int(start_frac * total_steps)
        ramp_end = int(full_frac * total_steps)
        if step < ramp_start:
            return 0.0
        if step < ramp_end:
            return (step - ramp_start) / max(ramp_end - ramp_start, 1)
        return 1.0

    if frac < start_frac:
        return 0.0
    if frac < full_frac:
        return (frac - start_frac) / max(full_frac - start_frac, 1e-6)
    return 1.0


def transformer_gate_scale(
    elapsed_ms: float,
    max_wallclock_ms: float | None,
    ramp_frac: float,
    floor: float,
) -> float:
    """Transformer logit gate ramp: floor → 1.0 over the first `ramp_frac` of training.

    Suppresses transformer noise in early training so the model can learn from
    a clean bigram-dominant loss surface. Gradient still flows; only the logit
    contribution is gated. After ramp_frac of wallclock time, returns 1.0
    unconditionally.
    """
    if max_wallclock_ms is None or max_wallclock_ms <= 0.0 or ramp_frac <= 0.0:
        return 1.0
    frac = min(max(elapsed_ms / max_wallclock_ms, 0.0), 1.0)
    if frac >= ramp_frac:
        return 1.0
    return floor + (1.0 - floor) * (frac / ramp_frac)